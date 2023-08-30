# To run the plugin in a Docker image, run the following commands:
# docker build -t mattaconnect .
# docker run -it --rm --workdir /home/pi mattaconnect bash

# Windows dev: docker run -it --rm -p 5001:5001 -v "C:\matta\moonraker-mattaconnect-internal:/home/pi/moonraker-mattaconnect" -w /home/pi mattaconnect

FROM python:3.10-slim-bullseye AS runner

RUN apt-get update && apt-get install -y \
    git \
    virtualenv \
    python3 \
    sudo \
    nano \
    systemctl

WORKDIR /home/pi

# Set up the printer data folder
RUN mkdir -p printer_data/logs \
             printer_data/config \
             printer_data/gcodes

COPY .. moonraker-mattaconnect/

RUN useradd -ms /bin/bash pi

# Choose one of these
RUN echo 'pi ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/pi-nopasswd
# RUN echo 'pi:raspberry' | chpasswd

RUN usermod -aG sudo pi

RUN chown -R pi:pi /home/pi

USER pi

EXPOSE 5001

CMD ["bash"]

ENV USER=pi
