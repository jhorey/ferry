g = TitanFactory.open('/service/conf/titan.properties');
g.loadGraphSON('/service/scripts/gods.json');
println g.V('name','pluto').out('brother').name;