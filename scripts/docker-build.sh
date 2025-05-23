#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🏗️  Building Prefect Docker image...${NC}"

# Pre-compute version
VERSION=$(python -c "import versioningit; print(versioningit.get_version('.'))")
echo -e "${GREEN}📌 Version: $VERSION${NC}"

# Build with all optimizations
time DOCKER_BUILDKIT=1 docker build \
  --build-arg PREFECT_VERSION=$VERSION \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --progress=plain \
  -t prefect:$VERSION \
  -t prefect:latest \
  .

echo -e "${GREEN}✅ Build complete!${NC}"
docker run --rm prefect:latest prefect version