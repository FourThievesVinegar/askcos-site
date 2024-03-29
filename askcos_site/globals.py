"""
Data and model instances for global use in ``askcos_site``.
"""

from pymongo import MongoClient
# Setting logging low
from rdkit import RDLogger
lg = RDLogger.logger()
lg.setLevel(RDLogger.CRITICAL)

import askcos.global_config as gc
from askcos.prioritization.precursors.scscore import SCScorePrecursorPrioritizer
from askcos.interfaces.template_transformer import TemplateTransformer
from askcos.utilities.buyable.pricer import Pricer
from askcos_site.celery import app

################################################################################
# Database client
db_client = MongoClient(gc.MONGO['path'], gc.MONGO['id'], connect=gc.MONGO['connect'])

################################################################################
# Database collections
reaction_db = db_client[gc.REACTIONS['database']][gc.REACTIONS['collection']]

chemical_db = db_client[gc.CHEMICALS['database']][gc.CHEMICALS['collection']]

buyables_db = db_client[gc.BUYABLES['database']][gc.BUYABLES['collection']]

solvent_db = db_client[gc.SOLVENTS['database']][gc.SOLVENTS['collection']]

retro_templates = db_client[gc.RETRO_TEMPLATES['database']][gc.RETRO_TEMPLATES['collection']]

forward_templates = db_client[gc.FORWARD_TEMPLATES['database']][gc.FORWARD_TEMPLATES['collection']]

################################################################################
# Retro Transformer
retro_transformer = TemplateTransformer(load_all=False, use_db=True, TEMPLATE_DB=retro_templates)
RETRO_CHIRAL_FOOTNOTE = 'Using {} chiral retrosynthesis templates from {}/{}'.format(
    gc.RELEVANCE_TEMPLATE_PRIORITIZATION['reaxys']['output_size'],
    gc.RETRO_TEMPLATES['database'],
    gc.RETRO_TEMPLATES['collection']
)

################################################################################
# Pricer
pricer = Pricer()
pricer.load()
print('Loaded global pricer.')

################################################################################
# SCScorer
scscorer = SCScorePrecursorPrioritizer()
scscorer.load_model(model_tag='1024bool')
print('Loaded global SCScorer.')
