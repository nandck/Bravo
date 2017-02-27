#pragma once

#include <thread>
#include <vector>

#include "TerrainTile.h"

#include "util/AsyncJobHandler.h"

/**
 * @brief Class to manage asynchronous terrain loading
 * Defines a terrain update job which involves retrieving
 * terrain data and processing it into vertex buffer data
 * which is used to update the OSG node.
 *
 * TODO: Is asynchronous updating of the Geode thread safe?
 */
class TerrainUpdater
{
public:
    TerrainUpdater() {}

    void process(TerrainTile* tile);

};

typedef AsyncJobHandler<TerrainUpdater, TerrainTile*> AsyncTerrainUpdater;
