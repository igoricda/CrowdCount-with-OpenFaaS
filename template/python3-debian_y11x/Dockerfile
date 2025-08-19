ARG PYTHON_VERSION=3.11
FROM --platform=${TARGETPLATFORM:-linux/amd64} ghcr.io/openfaas/classic-watchdog:0.3.1 AS watchdog
FROM --platform=${TARGETPLATFORM:-linux/amd64} python:${PYTHON_VERSION}

ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Allows you to add additional packages via build-arg
ARG ADDITIONAL_PACKAGE=libgl1-mesa-glx

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog
RUN apt-get update \
    && apt-get install -y ca-certificates curl libglib2.0-0 libgl1-mesa-glx ${ADDITIONAL_PACKAGE} \
    && rm -rf /var/lib/apt/lists/


# Add non root user
RUN groupadd app && useradd -r -g app app

WORKDIR /home/app/

COPY index.py           .
COPY requirements.txt   .

RUN chown -R app /home/app && \
    mkdir -p /home/app/python && chown -R app /home/app
USER app

# Variáveis de ambiente
ENV PATH=$PATH:/home/app/.local/bin:/home/app/python/bin/
ENV PYTHONPATH=$PYTHONPATH:/home/app/python
ENV TMPDIR=/home/app/tmp
# Set Ultralytics config directory to avoid home permission issues
ENV YOLO_CONFIG_DIR=/home/app/tmp/Ultralytics

# Optional: suppress verbose logs
ENV YOLO_VERBOSE=False

# Diretórios essenciais
RUN mkdir -p /home/app/tmp \
    && mkdir -p /home/app/python \
    && mkdir -p /home/app/function \
    && touch /home/app/function/__init__.py

# Copia os requirements antes (pra cache funcionar se nada mudar)
COPY function/requirements.txt /home/app/function/

# Define o diretório de trabalho
WORKDIR /home/app/function/

# Instala pacotes direto na pasta alvo pra economizar espaço
# Junta todos os pip em um único comando (mais rápido e menos camadas)
RUN pip install --no-cache-dir --target=/home/app/python \
    ultralytics\
    opencv-python\
    numpy \
    requests \
    Pillow \
    python-multipart \
    pickle-mixin \
    pyyaml 


WORKDIR /home/app/function/
COPY function/requirements.txt	.
#yolo
RUN curl -L -o /home/app/function/yolov11x.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x.pt

	
WORKDIR /home/app/

USER root

COPY function           function

# Allow any user-id for OpenShift users.
RUN chown -R app:app ./ && \
    chmod -R 777 /home/app/python

USER app

ENV fprocess="python3 index.py"
EXPOSE 8080 

HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1

CMD ["fwatchdog"]
