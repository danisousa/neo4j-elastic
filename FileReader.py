import json

# BBDD
from elasticsearch import Elasticsearch
from py2neo import Graph, Node, Relationship
from py2neo.matching import *

# Dependency Tree
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, Comment, tostring, ElementTree


class FileReader():
    # Find if the edge is between repository or component

    def __init__(self, connection):
        self.connection = connection

    def findType(tree, elements):
        
        types = {"sourceType":"", "targetType":""}
        types = json.loads(json.dumps(types))
        
        for elem in tree.iter():
            if(elem.attrib.get('id') == elements['source']):
                for subelem in elem.iter():
                    if(subelem.tag.split('}')[1] == 'NodeLabel'):
                        info = subelem.text.split(':')
                        if(len(info) == 4):
                            types['sourceType'] = "REPOSITORY"
                        else:
                            types['sourceType'] = "LIBRARY"
                            
            if(elem.attrib.get('id') == elements['target']):
                for subelem in elem.iter():
                    if(subelem.tag.split('}')[1] == 'NodeLabel'):
                        info = subelem.text.split(':')
                        if(len(info) == 4):
                            types['targetType'] = "REPOSITORY"
                        else:
                            types['targetType'] = "LIBRARY"

        return types


    def find_ids(tree, elements):
        types = {"sourceID":"", "targetID":""}
        types = json.loads(json.dumps(types))
        
        for elem in tree.iter():
            if(elem.attrib.get('id') == elements['source']):
                for subelem in elem.iter():
                    if(subelem.tag.split('}')[1] == 'NodeLabel'):
                        info = subelem.text.split(':')
                        if(len(info) == 4):
                            types['sourceID'] = info[1]
                        else:
                            new_id = info[1]+'@'+info[3]
                            types['sourceID'] = new_id
                            
            if(elem.attrib.get('id') == elements['target']):
                for subelem in elem.iter():
                    if(subelem.tag.split('}')[1] == 'NodeLabel'):
                        info = subelem.text.split(':')
                        if(len(info) == 4):
                            types['targetID'] = info[1]
                        else:
                            new_id = info[1]+'@'+info[3]
                            types['targetID'] = new_id

        return types

    # Parse XML
    def parse_xml(path_to_file, branch):
        # Parse the dependency tree
        tree = ET.parse(path_to_file)

        # For each element in the XML
        for elem in tree.iter():
            
            # If element is a Node
            if(elem.tag.split('}')[1] == 'node'):
                id = elem.attrib.get('id')
                #print('{}  {}'.format(elem.tag.split('}')[1], elem.attrib))
                for subelem in elem.iter():
                    if(subelem.tag.split('}')[1] == 'NodeLabel'):
                        info = subelem.text.split(':')
                        
                        # If it is the repo info
                        if(len(info) == 4):
                            # Create repo document
                            docu = {"id":info[1], "origin":info[0], "packing_type":info[2], "technology":"java"}
                            docu = json.loads(json.dumps(docu))
                            create_node(docu, "REPOSITORY")
                        elif(len(info) == 5):
                            # Create dependency Document
                            dep_id = info[1]+'@'+info[3]
                            docu = {"id":dep_id, "origin":info[0], "name":info[1], "packing_type":info[2], 
                                    "version":info[3], "validated":"true", "technology":"java"}
                            docu = json.loads(json.dumps(docu))
                            create_node(docu, "LIBRARY")       

        for elem in tree.iter():
            if(elem.tag.split('}')[1] == 'edge'):
                atributos = json.loads(json.dumps(elem.attrib))
                types = findType(tree, atributos)
                elems_ids = find_ids(tree, atributos)
                create_edge(elems_ids, types, branch)

    # Create document of repository in database
    def create_node_repo_document(repo):
        exists = NodeMatcher(self.connection).match('LIBRARY', id=repo['name']).first()
        # Check if exists
        if (exists is None):

            # Create Node in Neo4J
            new_node = Node('REPOSITORY', id=repo['name'], technology= 'javascript')
            self.connection.create(new_node)
            
    # Create document of dependency in database
    def create_node_depend_document(dep_data, dep_name):
        
        #dep_id = dep_name+'@'+dep_data['version']
        dep_id = dep_data['from']
        exists = NodeMatcher(self.connection).match('LIBRARY', id=dep_id).first()
        
        # Check if exists
        if (exists is None):
            
            # Create Node in Neo4J
            new_node = Node('LIBRARY', name=dep_name, 
                                origin=dep_data['from'], 
                                version=dep_data['version'], 
                                id=dep_id, 
                                validated= 'true', 
                                technology= 'javascript')
            
            self.connection.create(new_node)
        
    # Create document of relationship in database
    def create_node_edge_document(parent, origin, parent_type, branch):
        
        source = NodeMatcher(self.connection).match(parent_type, id=parent).first()
        destiny = NodeMatcher(self.connection).match("LIBRARY", id=origin['from']).first()
        
        # Check if exists
        if (source is not None and destiny is not None):
            depends = Relationship(source, branch , destiny)
            self.connection.create(depends)
            
    # Check if key has '/'
    def check_key_format(key):
        clave = key
        if("/" in key):
            clave = clave.replace("/", ":")
        return clave
        
    def get_depend_depth(source, parent, from_type, branch):
            
        # Check if it has dependencies at this level
        if ('dependencies' in source):
            deps = source['dependencies']

            # For each dependency
            for dep in deps:
                create_node_depend_document(deps[dep], dep)
                create_node_edge_document(parent, deps[dep], from_type, branch)
                get_depend_depth(deps[dep], deps[dep]['from'], 'LIBRARY', branch)
                
    # Read JSON with npm dependencies
    def read_JSON(json_path, branch):

        with open(json_path) as f:
            data = json.load(f)

            create_node_repo_document(data)
            get_depend_depth(data, data['name'], 'REPOSITORY', branch)