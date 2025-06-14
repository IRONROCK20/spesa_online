ARG BUILD_FROM=hassioaddons/base-python:5.2.0
FROM ${BUILD_FROM}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install pip and build tools, then clean up
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3-pip build-essential \
 && python3 -m pip install --no-cache-dir \
      flask \
      docker \
      gunicorn \
      requests \
 && apt-get remove --purge -y build-essential \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY . /

EXPOSE 9007
CMD ["gunicorn", "-b", "0.0.0.0:9007", "app:app"]
