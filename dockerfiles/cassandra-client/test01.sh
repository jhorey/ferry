#!/bin/bash

if [ $1 == "cql" ]; then
	su drydock -c '/service/bin/cqlsh -f /service/scripts/testusers.db'
elif [ $1 == "natural" ]; then
	su drydock -c '/service/packages/titan/bin/gremlin.sh -e /service/scripts/naturalgraph.groovy'
elif [ $1 == "gods" ]; then
	su drydock -c '/service/packages/titan/bin/gremlin.sh -e /service/scripts/loadgods.groovy'
fi