# should use official image if available someday
FROM tclesius/unit-1.31.1-python3.12

WORKDIR /usr/src/app/

ENV PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PYTHONUNBUFFERED=1

RUN pip install -U pip setuptools wheel -q && \
    pip install poetry -q

COPY ./pyproject.toml ./poetry.lock ./

RUN poetry config installer.max-workers 10
RUN poetry install --only main --no-root --sync --no-cache

COPY . .

COPY ./unit.config.json /docker-entrypoint.d/config.json
