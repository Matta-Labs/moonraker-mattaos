<p align="center">
  <img
    src="https://uploads-ssl.webflow.com/63fa465ee0545971ce735482/64883f3b58342c1b87033b6d_Emblem_Black.svg"
    alt="Matta Logo"
    style="width: 90px"
  />
</p>
<h1 align="center" style="margin-bottom: 20px">
  <a href="https://matta.ai">MattaConnect</a>
</h1>

<p align="center">
  Connect your Moonraker-connected klipper printers to
  <a href="https://os.matta.ai">MattaOS</a>, for remote control, AI-powered
  error detection, fleet management, and more!
</p>


- [Installation](#installation)
- [Usage](#usage)
- [Workflow (on raspberrypi)](#workflow-on-raspberrypi)
- [Workflow (with Docker)](#workflow-with-docker)
- [Custom configurations](#custom-configurations)
  - [Set up a dev environment (debugging)](#set-up-a-dev-environment-debugging)
  - [Creating a service](#creating-a-service)
  - [Creating a cfg file](#creating-a-cfg-file)


# Installation 

First rsync the plugin over from computer:

```bash
cd moonraker-mattaconnect
rsync -avh "../moonraker-mattaconnect" "pi@raspberrypi.local:~/."
```

Then install the plugin in the pi with the `install.sh` script:

```bash
cd ~/moonraker-mattaconnect
./install.sh
```

To uninstall, use the `uninstall.sh` script:
```bash
cd ~/moonraker-mattaconnect
./uninstall.sh
```

# Usage 

After installing, the service should be up and running, and we can check with `sudo systemtl status moonraker-mattaconnect`.

We can check the service by:
- `tail -f ~/printer_data/logs/moonraker-mattaconnect.log`
- Going to [raspberrypi.local:5001](http://raspberrypi.local:5001) 


# Workflow (on raspberrypi)

First time: 
```bash
cd moonraker-mattaconnect
# in computer: scp so that the name changes
scp -r "../moonraker-mattaconnect-internal" "pi@damjanpi.local:~/moonraker-mattaconnect"

# in pi
cd ~/moonraker-mattaconnect
./install.sh

# Solve bug of systemctl not running properly in bash manually
sudo systemctl enable moonraker-control-plugin        
sudo systemctl daemon-reload
sudo systemctl start moonraker-control-plugin
sudo systemctl status moonraker-control-plugin 
```

Afterwards:
```bash
# in computer
rsync -avh "../moonraker-mattaconnect" "pi@raspberrypi.local:~/."

# in pi
sudo systemctl restart moonraker-mattaconnect
# or simply restart in MainsailOS -> power button -> moonraker-mattaconnect,

```

# Workflow (with Docker)

First time: 
```bash
docker build -t mattaconnect .
docker run -it --rm --workdir /home/pi mattaconnect bash

cd moonraker-mattaconnect
./install.sh

# Temp fix for service not starting:
sudo systemctl restart moonraker-mattaconnect

# To view logs:
tail -f ~/printer_data/logs/moonraker-mattaconnect.log
```


# Custom configurations
The following will detail the steps to setup configurations without the install.sh script

## Set up a dev environment (debugging)
In computer:
```bash
rsync -avh "../moonraker-mattaconnect" "pi@raspberrypi.local:~/."
```

Then in raspberry pi:
```bash
cd moonraker-mattaconnect
virtualenv -p /usr/bin/python3 --system-site-packages ~/moonraker-mattaconnect-env
# Or: python3 -m venv ~/moonraker-mattaconnect-env # both seem to work fine
source ~/moonraker-mattaconnect-env/bin/activate
pip install -e .
```

Start app if we want to test it
```bash
python3 app.py
```


## Creating a service

Create a service file:

```bash
sudo nano /etc/systemd/system/moonraker-mattaconnect.service
```

Now fill it in with this format:

```bash
[Unit]
Description=Moonraker Control Plugin
After=network-online.target moonraker.service

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/moonraker-mattaconnect
ExecStart=/home/pi/moonraker-mattaconnect-env/bin/python3 /home/pi/moonraker-mattaconnect/app.py
Restart=always
RestartSec=5
```

Then enable, start and check the service:

```bash
sudo systemctl enable moonraker-mattaconnect
sudo systemctl daemon-reload
sudo systemctl start moonraker-mattaconnect

# To check if the service is running
sudo systemctl status moonraker-mattaconnect
```

## Creating a cfg file

Create a cfg file:

```bash
sudo nano ~/printer_data/config/moonraker-mattaconnect.cfg
```

Fill it with our default cfg settings

```bash
[moonraker_control]
enabled = true
printer_ip = localhost
printer_port = 7125
```

Now if we should be able to change the config file from MainsailOS by accessing MainsailOS -> Machine tab -> `moonraker-mattaconnect.cfg`.