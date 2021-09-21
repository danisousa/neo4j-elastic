# Utils
import json
import os
from os import path
import subprocess
import time
from datetime import datetime

# Dependency Tree
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, Comment, tostring, ElementTree

# BBDD
from elasticsearch import Elasticsearch
from py2neo import Graph, Node, Relationship
from py2neo.matching import *

RAMAS = ["develop", "master"]

CONNECT = Graph("bolt://localhost:7687", password="admin")

# Delete all DB
def clean_db():
    delete_query = "MATCH p=()-->() DELETE p"
    connection.run(delete_query)
    delete_query = "MATCH (p) DELETE p"
    connection.run(delete_query)
    print("Deleted DB data")
    
# Create node
def create_node(data, tipo):
    exists = NodeMatcher(connection).match(tipo, id=data['id']).first()
    
    # Check if exists
    if (exists is None):
        
        # Create Node in Neo4J
        new_node = Node(tipo, **data)
        connection.create(new_node)
                
# Create relationship
def create_edge(vertices, tipos, branch):
    source = NodeMatcher(connection).match(tipos['sourceType'], id=vertices['sourceID']).first()
    destiny = NodeMatcher(connection).match(tipos['targetType'], id=vertices['targetID']).first()
    
    # Check if exists
    if (source is not None and destiny is not None):
        depends = Relationship(source, branch , destiny)
        connection.create(depends)
        
    #else:
    #    print("{} - {}".format(vertices['sourceID'], vertices['targetID']))
        
# Update node 
def update_node(dep_name, dep_version, dep_field, dep_value):
    query = 'MATCH (p:LIBRARY) WHERE p.id="{name}@{version}" SET p.{field} = "{new_value}" RETURN p'.format(name=dep_name,
                                                                                                          version=dep_version,
                                                                                                          field=dep_field,
                                                                                                          new_value=dep_value)
    
    result = connection.run(query)
    
    print(result.data()[0]['p'])
    
# Search node
def search_node(dep_name, dep_version):
    query = 'MATCH (p:LIBRARY) WHERE p.id = "{name}@{version}" RETURN p.id'.format(name=dep_name,
                                                                            version=dep_version)
    
    cursor = connection.run(query).data()
    return cursor[0]['p.id']

# Get shortest path between node and not validated one
def get_path(dep_name, branch):
    query_check = 'MATCH (a), (b) WHERE (a)-[*]-(b) AND a.validated="false" AND b.id="{}" RETURN a.id, b.id'.format(dep_name)
    result = connection.run(query_check).data()

    if(len(result)>=1):
        
        unvalid_dep = result[0]['a.id']
        query_search = 'MATCH (from:REPOSITORY {{ id:"{}" }}) , (to:LIBRARY {{ id: "{}" }}) , path = (from)-[:{}*]->(to) RETURN path AS shortestPath, Nodes(path) LIMIT 1'.format(dep_name, unvalid_dep, branch)
        path = connection.run(query_search).data()
        
        if(len(path)>=1):
            result_path = path[0]
            print("{} - {} - KO".format(dep_name, branch))
            print('###############################################')
            tab = '\t'
            print(dep_name)
            for idx, nodo in enumerate(result_path['Nodes(path)']):
                if idx != 0:
                    print(tab*idx + '|')
                    print(tab*idx + nodo['id'])
                    
            return 'KO'
            
    else:
        print("{} - {} - OK".format(dep_name, branch))
        return 'OK'

# Check if one node is affected by not validated deps
def check_node(dep_type, dep_name):
    
    for rama in ramas:
        
        query_check = 'MATCH (a), (b) WHERE (a)-[*]-(b) AND a.validated="false" AND b.id="{}" RETURN a.id, b.id'.format(dep_name)
        result = connection.run(query_check).data()[0]

        if(len(result)>=1):

            unvalid_dep = result['a.id']
            query_search = 'MATCH (from:{} {{ id:"{}" }}) , (to:LIBRARY {{ id: "{}" }}) , path = (from)-[:{}*]->(to) RETURN path AS shortestPath, Nodes(path) LIMIT 1'.format(dep_type, dep_name, unvalid_dep, rama)

            if len(connection.run(query_search).data()) > 0:
                path = connection.run(query_search).data()[0]

                '''
                print(path['Nodes(path)'][0]['id'])
                print(path['Nodes(path)'][1]['id'])
                print(path['Nodes(path)'][len(path['Nodes(path)'])-1]['id'])
                '''

                return rama, path['Nodes(path)'][1]['id'], path['Nodes(path)'][len(path['Nodes(path)'])-1]['id']

            else:
                print("NODE {} in branch {} - OK".format(dep_name, branch))
    
    return 0

#update_node("hamcrest-core", "1.3", "validated", "false")
#search_node("hamcrest-core", "1.3")
check_node("LIBRARY", "crypto@3.6.0")