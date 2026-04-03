FROM node:20-slim

ARG HOST_UID=501
ARG HOST_GID=20
ENV USER=claude

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl nano mc ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*

# Create user matching host UID/GID
RUN groupadd -o -g ${HOST_GID} $USER 2>/dev/null || true \
    && useradd -o -u ${HOST_UID} -g ${HOST_GID} -m -s /bin/bash $USER

USER $USER
WORKDIR /home/$USER

RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/home/$USER/.local/bin:${PATH}"

RUN echo '{"hasCompletedOnboarding":true,"theme":"dark"}' > ~/.claude.json

COPY --chown=$USER entrypoint.sh bridge_container.py chrome_native_host.py ./
RUN chmod +x ./entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["bash"]
