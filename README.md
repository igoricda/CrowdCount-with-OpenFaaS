# CrowdCount-with-OpenFaaS
Repository with files used in my scientific initiation, using serveless combined with inference models in fog and edge devices

## Devices

Fog:
- Conventional server (Ryzen 7 5700G with 64GB RAM)

Edge:
- Raspberry Pi 4B
- Repurposed XP4 TVBox (SoC Amlogic S905x4) with armbian OS
  
On the server, OpenFaaS CE was used as serverless framework, while the edge devices, used faasd, OpenFaaS lightweight version, appropriate for the edge.

## Install walkthrough

### Edge

Both devices used the same process to install faasd:

1. Via CLI, clone the faasd repository:
```
git clone https://github.com/openfaas/faasd
```
2. Change to the cloned directory:
```
cd faasd
```
3. Execute the install bash script:
```
./hack/install.sh
```
4. Verify status:
```
systemctl status faasd
systemctl status faasd-provider
```
5. Get the password:
```
 cat /var/lib/faasd/secrets/basic-auth-password
```

### Fog

In the server, Kubernetes was used to install OpenFaaS CE:

On host machine:

1. Copy ssh key to server with:
```
ssh-copy-id $USER@$IP
```

2. Install pre-requisites:
```
curl -sSL https://get.arkade.dev | sudo sh
arkade get kubectl
arkade get k3sup
```

3. Install Kubernetes with k3sup and k3s (k3sup uses password-less login by default):

```
export IP=$IP # find the ip address of the server
k3sup install --ip $IP --user $USER --ssh-key ~/.ssh/id_rsa
```

4. After it, you will receive a kubeconfig file in your local directory, with instructions on how to use it:
```
export KUBECONFIG=$PATH/kubeconfig
```

5. To find the node and check if it is ready:
```
kubectl config use-context default
kubectl get node -o wide
kubectl top node
kubectl top pod --all-namespaces
```

6. To install openfaas on the node:
```
arkade install openfaas
```

7. A set of commands will be printed on the terminal:
```
kubectl -n openfaas get deployments -l "release=openfaas, app=openfaas"
kubectl rollout status -n openfaas deploy/gateway
kubectl port-forward -n openfaas svc/gateway 8080:8080 &
```

8. Get the password:
```
echo $(kubectl -n openfaas get secret basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode)
```

## Usage

### faas-cli 

To use the frameworks, the faas-cli is needed, it can be installed via CLI with:
```
arkade get faas-cli
```
or
```
curl -sSL https://cli.openfaas.com | sudo sh
```
or
```
brew install faas-cli
```

### Create functions

To create functions, there is a necessity to be logged on docker on your PC. This example will use a python function:

1. Install the template repository:
```
faas-cli template store pull python3-http-debian
```
The template's Dockerfile is customizable, to install some packages, resources, have a specific file structure etc.. In this case study, all functions used a customized Dockerfile, to install the inference models and its dependencies, with sections like:
```
ARG ADDITIONAL_PACKAGE=libgl1-mesa-glx

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog
RUN apt-get update \
    && apt-get install -y ca-certificates curl libglib2.0-0 libgl1-mesa-glx ${ADDITIONAL_PACKAGE} \
    && rm -rf /var/lib/apt/lists/
```
and
```
RUN curl -L -o /home/app/function/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
```
If not available at the store, this template file is available in this repository.

2. Create a new instance of the template:
```
faas-cli new <function name> --lang python3-debian --prefix <your docker user>
```
A new directory with the function name will be created and a .yml file with the same name, this file is customizable, as example, one of the containers used in this study:

```
version: 1.0
provider:
  name: openfaas
  gateway: http://127.0.0.1:8080
functions:
  crowdcountyolo:
    lang: python3-debian_y11
    handler: ./crowdcountyolo
    image: igoricda/crowdcountyolo:latest
    environment:
      max_inflight: 3
    build_args:
        ADDITIONAL_PACKAGE: "cmake ninja-build pkg-config git gcc libgtk-3-0 libgtk-3-dev libavformat-dev libavcodec-dev libswscale-dev python3-dev"
        PYTHON_VERSION: 3.11
```

In the directory, there will be a file handler.py, with the function that will be executed by the framework

3. To implant the function, it is needed to be authenticated in the chosen device:
```
faas-cli login --username admin --password $PASSWORD --gateway $HOST_IP:$PORT #Port is in default 8080 on faasd and 31112 on kubernetes 
```

4. There are differences for the server and edge devices, because of the differente architectures, for edge devices, it is needed to specify the architecture first, with publish:
```
faas-cli publish -f <filename>.yml --platforms linux/arm64

faas-cli deploy -f <filename>.yml --gateway $IP:$PORT
```
For the x86 server, both commands are combined with:
```
faas-cli up -f <filename>.yml --gateway $IP:$PORT
```
Sometimes, a timeout flag is needed ```--timeout 5m ```

5. If succesfull, code 200 will be returned and you will be able to invoke the function with
```
faas-cli invoke <function name>
```
Which will send an HTTP request for the function.


