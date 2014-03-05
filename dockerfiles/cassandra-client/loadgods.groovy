g = TitanFactory.open('/cassandra/conf/titan.properties');
g.loadGraphSON('/cassandra/scripts/gods.json');
g.V('name','pluto').out('brother').name;