terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 3.0.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "Test" {
  name     = "test-resources"
  location = "East US"
  tags = {
    environment = "dev"
  }
}

resource "azurerm_virtual_network" "Test-vnet" {
  name                = "test-network"
  resource_group_name = azurerm_resource_group.Test.name
  location            = azurerm_resource_group.Test.location
  address_space       = ["10.123.0.0/16"]

  tags = {
    environment = "dev"
  }
}

resource "azurerm_subnet" "Test-subnet" {
  name                 = "test-subnet"
  resource_group_name  = azurerm_resource_group.Test.name
  virtual_network_name = azurerm_virtual_network.Test-vnet.name
  address_prefixes     = ["10.123.1.0/24"]
}

resource "azurerm_network_security_group" "Test-sg" {
  name                = "test-sg"
  location            = azurerm_resource_group.Test.location
  resource_group_name = azurerm_resource_group.Test.name
  tags = {
    environment = "dev"
  }
}

resource "azurerm_network_security_rule" "Test-dev-rule" {
  name                        = "test-dev-rule"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.Test.name
  network_security_group_name = azurerm_network_security_group.Test-sg.name
}

resource "azurerm_subnet_network_security_group_association" "Test-sg-association" {
  subnet_id                 = azurerm_subnet.Test-subnet.id
  network_security_group_id = azurerm_network_security_group.Test-sg.id
}

resource "azurerm_public_ip" "Test-ip" {
  name                = "test-ip"
  location            = azurerm_resource_group.Test.location
  resource_group_name = azurerm_resource_group.Test.name
  allocation_method   = "Dynamic"

  tags = {
    environment = "dev"
  }
}

resource "azurerm_network_interface" "Test-nic" {
  name                = "test-nic"
  location            = azurerm_resource_group.Test.location
  resource_group_name = azurerm_resource_group.Test.name
  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.Test-subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.Test-ip.id
  }
  tags = {
    environment = "dev"
  }
}

resource "azurerm_linux_virtual_machine" "Test-vm" {
  name                = "test-machine"
  resource_group_name = azurerm_resource_group.Test.name
  location            = azurerm_resource_group.Test.location
  size                = "Standard_F2"
  admin_username      = "adminuser"
  network_interface_ids = [
    azurerm_network_interface.Test-nic.id,
  ]

  custom_data = filebase64("customdata.tpl")

  admin_ssh_key {
    username   = "adminuser"
    public_key = file("~/.ssh/testazkey.pub")
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }

  provisioner "local-exec" {
    command = templatefile("${var.host_os}-ssh-script.tpl", {
        hostname = self.public_ip_address,
        user = "adminuser",
        identityfile = "~/.ssh/testazkey"
    })
    interpreter = ["bash", "-c"]
  }

  tags = {
    environment = "dev"
  } 
}

data "azurerm_public_ip" "Test-ip-data" {
    name = azurerm_public_ip.Test-ip.name
    resource_group_name = azurerm_resource_group.Test.name

}

output "public_ip_address" {
    value = "${azurerm_linux_virtual_machine.Test-vm.name} : ${data.azurerm_public_ip.Test-ip-data.ip_address}"

}
resource "aws_s3_bucket" "test" {
  bucket = "my-test-bucket"
  acl    = "public-read"
}

resource "aws_s3_bucket" "insecure_test" {
  bucket = "ml-training-data"
  acl    = "public-read"
}

resource "aws_db_instance" "main" {
  identifier        = "prod-db"
  engine            = "mysql"
  instance_class    = "db.t3.micro"
  username          = "admin"
  password          = "hardcoded-password-123"
  skip_final_snapshot = true
}
