import sys
from twisted.internet import reactor
from twisted.web import proxy, server

def main():
    """
    Run a reverse proxy for the NameNode, YARN master, and JobTracker. 
    """
    server = sys.argv[1]
    port = int(sys.argv[2])

    site = server.Site(proxy.ReverseProxyResource(server, port, ''))
    reactor.listenTCP(port, site)
    reactor.run()

if __name__ == "__main__":
    main()
