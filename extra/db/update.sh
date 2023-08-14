#!/bin/bash -x

# check the latest release of the gnaf-loader
LAST_TAG=$(curl -s https://api.github.com/repos/minus34/gnaf-loader/releases/latest | jq -r .tag_name)

# check if we already have our derived image
IMG_NAME=lukeprior/nbn-upgrade-map-db
docker manifest inspect $IMG_NAME:$LAST_TAG > /dev/null
if [ $? -eq 0 ]; then
    # already exists - do nothing
    echo "$IMG_NAME:$LAST_TAG already exists, skipping..."
else
    # image doesn't exist - download DB dump, build and push
    DUMP_FILE="gnaf-${LAST_TAG}.dmp"
    if [ -f "$DUMP_FILE" ]; then
        echo "$DUMP_FILE already exists, skipping download..."
    else
        echo "Downloading $DUMP_FILE..."
        curl --insecure "https://minus34.com/opendata/geoscape-${LAST_TAG}/${DUMP_FILE}" --output "./${DUMP_FILE}"
    fi
    echo "Building $IMG_NAME:$LAST_TAG..."
    docker build . --build-arg GNAF_LOADER_TAG=$LAST_TAG -t $IMG_NAME:$LAST_TAG -t $IMG_NAME:latest --progress=plain
    docker push $IMG_NAME:$LAST_TAG
    docker push $IMG_NAME:latest
fi
