IMAGE_NAME=tw-power-plant
CONTAINER_NAME=tw-power-plant
PYTHON=py

OPTIONS:=

ifeq ($(OS),Windows_NT)
VENV_SCRIPTS_ACTIVATE=venv\Scripts\activate
else
VENV_SCRIPTS_ACTIVATE=source env/bin/activate
endif

dockerbuild:
	docker build -t ${CONTAINER_NAME} .

dockerclean:
	docker stop ${CONTAINER_NAME} || true
	docker rm ${CONTAINER_NAME} || true

dockerrun: dockerclean
	docker run -d \
			--name ${CONTAINER_NAME} \
			--restart always \
			-v ${CURDIR}\data:\app\data \
			-p 8090:80 \
			${CONTAINER_NAME}

distclean:
	rm -rf venv

################################################

build: requirements.txt
	$(PYTHON) -m venv venv
	$(VENV_SCRIPTS_ACTIVATE); pip install -r requirements.txt
