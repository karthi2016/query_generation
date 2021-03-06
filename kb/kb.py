import requests
from multiprocessing import Pool
from contextlib import closing


def query(args):
    endpoint, q = args
    payload = (('query', q), ('format', 'application/json'))
    try:
        r = requests.get(endpoint, params=payload, timeout=60)
    except:
        return 0, None
    return r.status_code, r.json() if r.status_code == 200 else None

class KB(object):
    def __init__(self, endpoint, default_graph_uri=""):
        self.endpoint = endpoint
        self.default_graph_uri = default_graph_uri
        self.type_uri = "type_uri"

    def query(self, q):
        payload = (
            ('query', q),
            ('format', 'application/json'))
        try:
            r = requests.get(self.endpoint, params=payload, timeout=60)
        except:
            return 0, None

        return r.status_code, r.json() if r.status_code == 200 else None

    def query_where(self, clauses, return_vars="*", count=False, ask=False):
        where = u"WHERE {{ {} }}".format(" .".join(clauses))
        if count:
            query = u"{} SELECT COUNT(DISTINCT {}) {}".format(self.query_prefix(), return_vars, where)
        elif ask:
            query = u"{} ASK {}".format(self.query_prefix(), where)
        else:
            query = u"{} SELECT DISTINCT {} {}".format(self.query_prefix(), return_vars, where)
        status, response = self.query(query)
        if status == 200:
            return response

    def __parallel_query(self, query_types):
        args = []
        for i in range(len(query_types)):
            args.append(
                (self.endpoint, u"{} ASK WHERE {{ {} }}".format(self.query_prefix(), query_types[i])))
        with closing(Pool(len(query_types))) as pool:
            query_results = pool.map(query, args)
            pool.terminate()
            results = []
            for i in range(len(query_results)):
                if query_results[i][0] == 200:
                    results.append((i, query_results[i][1]["boolean"]))
            return results

    def one_hop_graph(self, entity1_uri, relation_uri, entity2_uri=None):
        relation_uri = self.uri_to_sparql(relation_uri)
        entity1_uri = self.uri_to_sparql(entity1_uri)
        if entity2_uri is None:
            entity2_uri = "?u1"
        else:
            entity2_uri = self.uri_to_sparql(entity2_uri)
        query_types = [u"{ent2} {rel} {ent1}",
                       u"{ent1} {rel} {ent2}",
                       u"?u1 {type} {rel}"]
        where = ""
        for i in range(len(query_types)):
            where = where + u"UNION {{ values ?m {{ {} }} {{select <1> where {{ {} }} }} }}\n".format(i,
                query_types[i].format(rel=relation_uri, ent1=entity1_uri, ent2=entity2_uri, type=self.type_uri,
                     prefix=self.query_prefix()))
        where = where[6:]
        query = u"""{prefix}
SELECT DISTINCT ?m WHERE {{ {where} }}""".format(prefix=self.query_prefix(), where=where)

        status, response = self.query(query)
        if status == 200 and len(response["results"]["bindings"]) > 0:
            return response["results"]["bindings"]

    def two_hop_graph(self, entity1_uri, relation1_uri, entity2_uri, relation2_uri):
        relation1_uri = self.uri_to_sparql(relation1_uri)
        relation2_uri = self.uri_to_sparql(relation2_uri)
        entity1_uri = self.uri_to_sparql(entity1_uri)
        entity2_uri = self.uri_to_sparql(entity2_uri)

        query_types = [u"{ent1} {rel1} {ent2} . ?u1 {rel2} {ent1}",
                 u"{ent1} {rel1} {ent2} . {ent1} {rel2} ?u1",
                 u"{ent1} {rel1} {ent2} . {ent2} {rel2} ?u1",
                 u"{ent1} {rel1} {ent2} . ?u1 {rel2} {ent2}",
                 u"{ent1} {rel1} {ent2} . ?u1 {type} {rel2}"]
        return self.__parallel_query([item.format(rel1=relation1_uri, ent1=entity1_uri,
                              ent2=entity2_uri, rel2=relation2_uri,
                              type=self.type_uri) for item in query_types])

    @staticmethod
    def shorten_prefix():
        return ""

    @staticmethod
    def query_prefix():
        return ""

    @staticmethod
    def prefix():
        return ""

    @staticmethod
    def parse_uri(input_uri):
        pass

    @staticmethod
    def uri_to_sparql(input_uri):
        return input_uri.uri
