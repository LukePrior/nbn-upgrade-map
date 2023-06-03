#!/bin/bash -x

# check the latest release of the gnaf-loader
LAST_TAG=$(curl -s https://api.github.com/repos/minus34/gnaf-loader/releases/latest | jq -r .tag_name)

# check if we already have our derived image
IMG_NAME=lyricnz/nbn-upgrade-map-db
docker manifest inspect $IMG_NAME:$LAST_TAG > /dev/null
if [ $? -eq 0 ]; then
    # already exists - do nothing
    echo "$IMG_NAME:$LAST_TAG already exists, skipping..."
else
    # doesn't exist - build and push
    echo "Building $IMG_NAME:$LAST_TAG..."
    docker build . --build-arg GNAF_LOADER_TAG=$LAST_TAG -t $IMG_NAME:$LAST_TAG -t $IMG_NAME:latest --progress=plain
    docker push $IMG_NAME:$LAST_TAG
    docker push $IMG_NAME:latest
fi
