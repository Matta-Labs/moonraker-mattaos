<p align="center"><img src="https://uploads-ssl.webflow.com/63fa465ee0545971ce735482/64883f3b58342c1b87033b6d_Emblem_Black.svg" alt="Matta Logo" style="width:50px" /></p>
<h1 align="center" style="margin-bottom:20px"><a href="https://matta.ai">MattaOS</a> for Klipper</h1>
<img src="https://matta-os.fra1.cdn.digitaloceanspaces.com/site-assets/email_assets/VideoGridCover.png" />
<p>Connect your Klipper-enabled printers to <a href="https://os.matta.ai">MattaOS</a>, for remote control, AI-powered error detection, fleet management, and more!</p>

## 🧐 About

The plugin allows users to control their printers using our intuitive web-interface, <a href="https://os.matta.ai">MattaOS</a>. MattaOS brings Matta's data engine to Klipper, managing printer and webcam data, enabling next-level AI error detection and print job inspection. All that is required is a simple nozzle camera, and a 3D printer running Klipper.

Matta is working towards building full AI-powered closed-loop control of 3D printing, enabling perfect quality, every time. By being an early user of our software, you help us build towards this goal!
## ✨ Features

- 🛜 Remote printer control via MattaOS, our intuitive web-interface.
- ⚡️ Advanced error detection using Matta's cutting-edge AI.
- 📈 Keep track of your printing operations with printer analytics.
- 👀 G-code viewer and analysis.
- ⚙️ Controllable failure behaviour (notify, pause, stop).

<br/>
<div align="center"><img src="https://matta-os.fra1.cdn.digitaloceanspaces.com/site-assets/MattaOS.gif" width=650 /><p>Monitoring a print with MattaOS</p></div>
<br/>



## 🚀 Plugin Installation
    
Before installing, please ensure you have <a href="https://github.com/Arksine/moonraker">Moonraker</a>, the Python 3 based web server for communcation with Klipper, installed on your Pi. Moonraker comes pre-installed with both the MainsailOS and Fluidd Raspberry Pi images. If you do not have Moonraker installed, you can find the installation guide <a href="https://moonraker.readthedocs.io/en/latest/installation/">here</a>.

<b>We highly recommend using the MattaOS plugin with the MainsailOS Raspberry Pi image</b> (available through the <a href="https://www.raspberrypi.com/software/">Raspberry Pi Imager</a>).

It has also been tested on RaspberryPi OS wth KIAUH-installed prerequisite, but to a lesser extent

There are number of ways to install, please see below:

<details>
  <summary><b>Transfer plugin from computer</b></summary>
    <br/>

  First, clone this repository onto your computer, then:

  ```bash
  cd moonraker-mattaos
  scp -r "../moonraker-mattaos" "<piusername@pihostname>:~/moonraker-mattaos"
  rsync -avh "../moonraker-mattaos/." "<piusername@pihostname>:~/moonraker-mattaos/."
  ```

  SSH into your Pi, then install the plugin with the `install.sh` script:

  ```bash
  cd ~/moonraker-mattaos
  ./install.sh
  ```

  Check the plugin is running with:
  ```shell
  sudo systemctl status moonraker-mattaos
  ```

  If not, start it manually with:
  ```shell
  sudo systemctl enable moonraker-mattaos        
  sudo systemctl daemon-reload
  sudo systemctl start moonraker-mattaos  
  sudo systemctl status moonraker-mattaos 
  ```

  ✨ Thats it! Now the MattaOS plugin should be installed.

  To uninstall, use the `uninstall.sh` script:
  ```bash
  cd ~/moonraker-mattaos
  ./uninstall.sh
  ```

</details>
<details>
  <summary><b>Clone onto Pi via SSH</b></summary>
    <br/>

At first, you need to access the Raspberry Pi connected to the 3D printer which is running Klipper. This best way to do this is via `ssh`, e.g.

```shell
ssh username@hostname.local
```

*Note: the default username for Pis is `pi`.* <br/>
*Note: the default password for Pis is `raspberry` it should probably be changed if it is still the password.*

```shell
git clone https://github.com/Matta-Labs/moonraker-mattaos.git
```

```shell
cd ~/moonraker-mattaos
bash install.sh
```

Check the plugin is running with:
```shell
sudo systemctl status moonraker-mattaos
```

If not, start it manually with:
```shell
sudo systemctl enable moonraker-mattaos        
sudo systemctl daemon-reload
sudo systemctl start moonraker-mattaos  
sudo systemctl status moonraker-mattaos 
```

✨ Thats it! Now the MattaOS plugin should be installed.

To uninstall, use the `uninstall.sh` script:
```bash
cd ~/moonraker-mattaos
./uninstall.sh
```
</details>


## 📸 Nozzle Cameras

If you don't already have a nozzle camera installed, check our our <a href="https://github.com/Matta-Labs/camera-mounts">camera-mounts repository</a> to aid installation.

Also please feel free to contribute your own nozzle camera designs to the repo!
<br/>



## 🎈 Usage and Configuration

First sign-up for a free Matta account at <a>https://os.matta.ai</a>, then configure plugin settings to get started!

Create a new machine in MattaOS, copy the generated Authorisation token, then add this to the ```moonraker-mattaos.cfg``` file in your Pi, or using the helpful Mainsail config file editor. Then reboot your Pi with ```sudo reboot```, or the restart the plugin using the power options in Mainsail.

<br/>
<div align="center"><img src="https://matta-os.fra1.cdn.digitaloceanspaces.com/site-assets/KlipperPluginSetup.gif" width=650 /><p>Machine setup and plugin configuration workflow</p></div>
<br/>

Next go to ```http://<hostname>:5001``` and follow the instructions to locate your extruder nozzle tip.

<br/>
<div align="center"><img src="https://matta-os.fra1.cdn.digitaloceanspaces.com/site-assets/KlipperSnap.gif" width=650 /><p>Nozzle coordinates finder usage</p></div>
<br/>

In ```moonraker-mattaos.cfg``` there are a few variables which need to be configured for use:

<h3>Mandatory configuration variables</h3>
<details>
<summary><b>Authorisation token </b>(from MattaOS)</summary>
<br/>

1. Create a printer in MattaOS.
2. Copy the Authorisation token from the new printer's setup page.
3. Paste this into the ```auth_token``` variable in ```moonraker-mattaos.cfg```
4. Restart the plugin or reboot your Pi to connect!

<br/>

</details>

<details>
<summary><b>WebRTC Stream URL*</b></summary>

<br/>

This is the streaming URL of your nozzle-cam streamer. The plugin only supports WebRTC streaming. The default value should be fine.

This will be ```http://localhost/webcam/webrtc```

<br/>

</details>
<details>
<summary><b>Camera Snapshot URL*</b></summary>
<br/>

This is the snapshot URL of your nozzle-cam streamer. The default value should be fine.

This will be ```http://localhost/webcam/?action=snapshot```

<br/>

</details>
<h3>Other configuration variables</h3>
<details>
<summary><b>Nozzle tip coordinates </b></summary>
<br/>

These are set via using the nozzle finder application at ```http://<hostname>:5001```.
<br/>
Alternatively, if you know the coordinates of the nozzle tip in your images, you can set them manually here.
</details>

<details>
<summary><b>Webcam controls</b></summary>
<br/>

These variables allow you to flip and rotate your webcam footage (for example if you have a camera mounted on its side for ease of integration).

<br/>

Simply set these values to ```true``` or ```false```, and see the changes reflected in the saved images in your <a href="https://os.matta.ai/main/print-jobs/view">MattaOS job history.</a>

<br/>

</details>
<br/>
<p>*required for AI-powered error detection</p>

<br/>


## 🔷 More About Matta

<div  align="center" >
  <img src="https://matta-os.fra1.cdn.digitaloceanspaces.com/site-assets/matta-about.png" alt="Matta info">
</div>
<br/>
At <a href="https://matta.ai"><strong>Matta</strong></a>, we are building AI to push the boundaries of manufacturing. We train neural networks using vision to become manufacturing copilots, enabling next-generation error correction, material qualitification and part QC.

<br/>
<br/>

<a href="https://matta.ai/greymatta"><strong>Check out the demo of our first-iteration AI, Grey-1</strong></a>


<br/>

## 📞 Contact 

Team Matta - [@mattalabs](https://twitter.com/mattalabs) - hello@matta.ai

Project Link: [https://github.com/Matta-Labs/moonraker-mattaos](https://github.com/Matta-Labs/moonraker-mattaos)

<p align="right">(<a href="#readme-top">back to top</a>)</p>
