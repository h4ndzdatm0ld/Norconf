ARG PYTHON_VER=3.9

FROM python:${PYTHON_VER} AS base

WORKDIR /usr/src/app

# Install poetry for dep management
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
ENV PATH="$PATH:/root/.poetry/bin"

# Enable this for testing with ^3.10.1
# RUN pip install cleo tomlkit poetry.core requests cachecontrol cachy html5lib pkginfo virtualenv lockfile

RUN poetry config virtualenvs.create false

# Install project manifest
COPY poetry.lock pyproject.toml ./

# Install production dependencies
RUN poetry install --no-root

FROM base AS test

COPY . .
# --no-root declares not to install the project package since we're wanting to take advantage of caching dependency installation
# and the project is copied in and installed after this step
RUN poetry install --no-interaction

# Runs all necessary linting and code checks
RUN echo 'Running Flake8' && \
    flake8 . && \
    echo 'Running Black' && \
    black --check --diff . && \
    echo 'Running Yamllint' && \
    yamllint . && \
    echo 'Running Pylint' && \
    find . -name '*.py' | xargs pylint  && \
    echo 'Running pydocstyle' && \
    pydocstyle .

ENTRYPOINT ["echo"]

CMD ["success"]
#############
# Final image
#
# This creates a runnable CLI container
FROM python:3.9-slim AS cli

WORKDIR /usr/src/app

COPY --from=base /usr/src/app /usr/src/app
COPY --from=base /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

COPY . .

ENTRYPOINT ["python"]

CMD ["norconf.py"]
