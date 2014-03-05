# Based on Dockerfile from Docker.io documentation. 
FROM base

RUN apt-get update;apt-get --yes install make python-pip python-setuptools
RUN pip install Sphinx==1.2.1
RUN pip install sphinxcontrib-httpdomain==1.2.0

CMD ["make", "-C", "/docs", "clean", "server"]
EXPOSE 8000