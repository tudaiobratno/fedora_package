FROM fedora:39

RUN dnf install -y --setopt=install_weak_deps=False --nodocs \
    sudo \
    util-linux \
    wget \
    nano \
    bash-completion \
    dnf-plugins-core \
    tree \
    python3-dotenv \ 
    python3-beautifulsoup4 \
    python3-prettytable \
    python3-requests \
  
    && rm -rf /var/cache /var/log/dnf* /var/log/yum.*

ARG USER_ID=100        
ARG GROUP_ID=100

RUN groupadd -g $GROUP_ID dev \
    && useradd -ms /bin/bash -u $USER_ID -g dev dev

RUN echo "dev:dev" | chpasswd \
    && echo "dev  ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/dev

USER dev

COPY fedora_pack.py /pr/fedora_pack.py

ENTRYPOINT [ "/bin/bash" ]
