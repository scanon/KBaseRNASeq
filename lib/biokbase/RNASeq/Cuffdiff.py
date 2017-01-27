import simplejson, sys, shutil, os, ast , re
from mpipe import OrderedStage , Pipeline
import glob, json, uuid, logging  , time ,datetime 
import subprocess, threading,traceback
from collections import OrderedDict
from pprint import pprint , pformat
import parallel_tools as parallel
from mpipe import OrderedStage , Pipeline
import contig_id_mapping as c_mapping 
import script_util
import handler_utils as handler_util
from biokbase.workspace.client import Workspace
from biokbase.auth import Token
import multiprocessing as mp
#import doekbase.data_api
#from doekbase.data_api
#from doekbase.data_api
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
try:
    from biokbase.HandleService.Client import HandleService
except:
    from biokbase.AbstractHandle.Client import AbstractHandle as HandleService
from biokbase.RNASeq.ExecutionBase import ExecutionBase
from biokbase.RNASeq import rnaseq_util
#import ExecutionBase.ExecutionBase as ExecutionBase

class CuffdiffException(Exception):
    pass

class Cuffdiff(ExecutionBase): 

    def __init__(self, logger, directory, urls, max_cores):
        super(self.__class__, self).__init__(logger, directory, urls, max_cores)

        # user defined shared variables across methods
        self.num_threads = None
	self.tool_used = "Cuffdiff"
	self.tool_version = "1.2.3"
    
    def prepare(self):
        # for quick testing, we recover parameters here
        ws_client = self.common_params['ws_client']
        hs = self.common_params['hs_client']
        params = self.method_params
        logger = self.logger
        token = self.common_params['user_token']
        cuffdiff_dir = self.directory

	self.details = rnaseq_util.get_details_for_diff_exp(logger,ws_client,hs,params['ws_id'],self.urls,cuffdiff_dir,params['expressionset_id'],token)
    	self.num_threads = mp.cpu_count()
	self.num_jobs = 1
	als = [] 
	for l in self.details['labels']:
                rep_files=",".join([ os.path.join(cuffdiff_dir+'/'+l,sub+'/accepted_hits.bam') for sub in os.listdir(os.path.join(cuffdiff_dir,l)) if os.path.isdir(os.path.join(cuffdiff_dir,l+'/'+sub))])
                als.append(rep_files)

        self.bam_files = " ".join([i for i in als])
        self.t_labels = ",".join(self.details['labels'])
        self.task_list = [self.__class__]		
    def runEach(self,task_list):
	 ### Call Cuffmerge function
	 cuffmerge_dir = os.path.join(self.directory,"cuffmerge")
	 merged_gtf = rnaseq_util.call_cuffmerge(self.directory,cuffmerge_dir,self.num_threads,self.details['gtf_file'],self.details['gtf_list_file'])
	 ### Run Cuffdiff
	 output_dir = os.path.join(self.directory,self.method_params['output_obj_name'])
	 cuffdiff_command = (' -p '+str(self.num_threads))

	 ### Setting Advanced parameters for Cuffdiff

         if('time_series' in self.method_params and self.method_params['time_series'] != 0) : cuffdiff_command += (' -T ')
         if('min_alignment_count' in self.method_params and self.method_params['min_alignment_count'] is not None ) : cuffdiff_command += (' -c '+str(self.method_params['min_alignment_count']))
         if('multi_read_correct' in self.method_params and self.method_params['multi_read_correct'] != 0 ): cuffdiff_command += (' --multi-read-correct ')
         if('library_type' in self.method_params and self.method_params['library_type'] is not None ) : cuffdiff_command += ( ' --library-type '+self.method_params['library_type'])
         if('library_norm_method' in self.method_params and self.method_params['library_norm_method'] is not None ) : cuffdiff_command += ( ' --library-norm-method '+self.method_params['library_norm_method'])
         try:
                cuffdiff_command += " -o {0} -L {1} -u {2} {3}".format(output_dir,self.t_labels,merged_gtf,self.bam_files)
                self.logger.info("Executing: cuffdiff {0}".format(cuffdiff_command))
                ret = script_util.runProgram(None,"cuffdiff",cuffdiff_command,None,self.directory)
                result = ret["result"]
		for line in result.splitlines(False):
                       self.logger.info(line)
                       stderr = ret["stderr"]
                       prev_value = ''
                       for line in stderr.splitlines(False):
                           if line.startswith('> Processing Locus'):
                                   words = line.split()
                                   cur_value = words[len(words) - 1]
                                   if prev_value != cur_value:
                                      prev_value = cur_value
                                      self.logger.info(line)
                                   else:
                                      prev_value = ''
                                      self.logger.info(line)
         except Exception,e:
		raise Exception(e)
                raise Exception("Error executing cuffdiff {0},{1}".format(cuffdiff_command,e))
	 try:
                 self.logger.info("Zipping Cuffdiff output")
                 out_file_path = os.path.join(self.directory,"{0}.zip".format(self.method_params['output_obj_name']))
                 script_util.zip_files(self.logger,output_dir,out_file_path)
         except Exception,e:
                 raise Exception("Error executing cuffdiff")
         try:
                 handle = script_util.upload_file_to_shock(logger,out_file_path)['handle']
         except Exception, e:
                 print " ".join(traceback.print_exc())
                 raise Exception("Failed to upload the Cuffdiff output files: {0}".format(" ".join(traceback.print_exc())))
	 ## Save object to workspace
         try:
                 self.logger.info("Saving Cuffdiff object to workspace")
                 cm_obj = { "tool_used" : self.tool_used,
                            "tool_version" : self.tool_version,
                            "condition" : self.details['labels'],
                            "genome_id" : self.details['genome_id'],
                            "expressionSet_id" : self.details['expressionset_id'],
                            "alignmentSet_id": self.details['alignmentset_id'],
                            "sampleset_id" : self.details['sampleset_id'],
                            "file" : handle
                           }
	 except Exception , e:
		raise Exception("Error Running Cuffdiff {0} ".format(e))
		
	 finally:
		return cm_obj

    def collect(self) :
	 output_name = self.method_params['output_obj_name']
	 res1= self.common_params['ws_client'].save_objects(
                                     {"workspace":self.method_params['ws_id'],
                                      "objects": [{
                                      "type":"KBaseRNASeq.RNASeqDifferentialExpression",
                                      "data":self.results[0],
                                      "name":output_name}]})
         self.returnVal = { 'output'  : output_name ,'workspace' : self.method_params['ws_id']}
