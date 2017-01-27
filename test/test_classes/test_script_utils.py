import unittest
import os
import time
import shutil
import json

from os import environ
try:
    from ConfigParser import ConfigParser  # py2
except:
    from configparser import ConfigParser  # py3

from pprint import pprint

from biokbase.workspace.client import Workspace as workspaceService
from GenomeFileUtil.GenomeFileUtilClient import GenomeFileUtil
from DataFileUtil.DataFileUtilClient import DataFileUtil
from biokbase.RNASeq import script_util

class ScriptUtilTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = environ.get('KB_AUTH_TOKEN', None)
        cls.token = token
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        #cls.ctx = MethodContext(None)
        #cls.ctx.update({'token': token,
        #                'provenance': [
        #                    {'service': 'GenomeFileUtil',
        #                     'method': 'please_never_use_it_in_production',
        #                     'method_params': []
        #                     }],
        #                'authenticated': 1})
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('KBaseRNASeq'):
            cls.cfg[nameval[0]] = nameval[1]
        cls.wsURL = cls.cfg['ws_url']
        cls.wsClient = workspaceService(cls.wsURL, token=token)
        cls.gfu = GenomeFileUtil(os.environ['SDK_CALLBACK_URL'], token=token) 

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        if hasattr(self.__class__, 'wsName'):
            return self.__class__.wsName
        suffix = int(time.time() * 1000)
        wsName = "test_KBaseRNASeq" + str(suffix)
        ret = self.getWsClient().create_workspace({'workspace': wsName})
        self.__class__.wsName = wsName
        return wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def prepare_genome(self):
        result = self.gfu.genbank_to_genome({'file':{'path':'./test/data/GCF_000005845.2_ASM584v2_genomic.gbff'},
                               'genome_name':'testGenome',
                               'workspace_name': self.getWsName()})
        return result
        
    def test_simple_upload(self):
        # fetch the test files and set things up
        result=self.prepare_genome()
        pprint(result)
        self.assertIsNotNone(result['genome_ref'])
        logger = script_util.stderrlogger(__file__)
        script_util.generate_fasta(logger,{},self.token,result['genome_ref'],'/kb/module/work/','test.fa')



