g = TitanFactory.open('/service/conf/titan.properties');

size = 100; ids = [g.addVertex().id]; rand = new Random();
(1..size).each{
    v = g.addVertex();
    u = g.v(ids.get(rand.nextInt(ids.size())))
	g.addEdge(v,u,'linked');
    ids.add(u.id);
    ids.add(v.id);
    if(it % 1000 == 0) 
	g.commit()
}

indegree = [:].withDefault{0}
    ids.unique().each{ 
	count = g.v(it).inE.count();
	indegree[count] = indegree[count] + 1;
    }
indegree.sort{a,b -> b.value <=> a.value}
println indegree