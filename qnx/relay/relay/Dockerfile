FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir websockets==15.0.1
RUN useradd -m -s /bin/bash tunnel \
 && usermod -p '*' tunnel \
 && mkdir -p /home/tunnel/.ssh && chmod 700 /home/tunnel/.ssh \
 && chown -R tunnel:tunnel /home/tunnel/.ssh \
 && mkdir -p /run/sshd
COPY sshd_config /etc/ssh/sshd_config
COPY wsbridge.py /opt/wsbridge.py
COPY start.sh /opt/start.sh
RUN chmod +x /opt/start.sh
CMD ["/opt/start.sh"]
