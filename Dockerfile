ARG CORE_VERSION=old

FROM fourthievesvinegar/askcos-core:$CORE_VERSION as core

USER root

RUN python -m pip install --upgrade pip

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && rm requirements.txt

# Use non-AVX version of tensorflow
COPY tensorflow-2.0.0a0-cp37-cp37m-linux_x86_64.whl tensorflow-2.0.0a0-cp37-cp37m-linux_x86_64.whl
RUN pip install tensorflow-2.0.0a0-cp37-cp37m-linux_x86_64.whl

COPY --chown=askcos:askcos . /usr/local/askcos-site

USER askcos

ENV PYTHONPATH=/usr/local/askcos-site:${PYTHONPATH}

RUN python /usr/local/askcos-site/manage.py collectstatic --noinput

LABEL site.version={VERSION} \
      site.git.hash={GIT_HASH} \
      site.git.date={GIT_DATE} \
      site.git.describe={GIT_DESCRIBE}
