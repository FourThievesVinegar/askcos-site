import json
import os
import time
from collections import defaultdict
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse

from askcos_site.askcos_celery.treebuilder.tb_c_worker import get_top_precursors
from askcos_site.askcos_celery.treebuilder.tb_coordinator_mcts import get_buyable_paths as get_buyable_paths_mcts
from askcos_site.globals import retro_transformer, RETRO_CHIRAL_FOOTNOTE, pricer
from askcos_site.main.models import BlacklistedReactions, BlacklistedChemicals, SavedResults
from askcos_site.main.utils import ajax_error_wrapper, resolve_smiles, is_banned
from askcos_site.main.views.users import can_control_robot


#@login_required
def retro(request, smiles=None, chiral=True, mincount=0, max_n=200):
    '''
    Retrosynthesis homepage
    '''
    context = {}

    # Set default inputs
    context['form'] = {}
    context['form']['template_prioritization'] = request.session.get('template_prioritization', 'Relevance')
    context['form']['precursor_prioritization'] = request.session.get('precursor_prioritization', 'RelevanceHeuristic')
    context['form']['template_count'] = request.session.get('template_count', '100')
    context['form']['max_cum_prob'] = request.session.get('max_cum_prob', '0.995')
    context['form']['filter_threshold'] = request.session.get('filter_threshold', '0.75')

    print(request)
    if request.method == 'POST':
        print(request)
        smiles = str(request.POST['smiles'])  # not great...
        context['form']['template_prioritization'] = str(
            request.POST['template_prioritization'])
        request.session['template_prioritization'] = context['form']['template_prioritization']
        context['form']['precursor_prioritization'] = str(
            request.POST['precursor_prioritization'])
        request.session['precursor_prioritization'] = context['form']['precursor_prioritization']

        if 'template_count' in request.POST:
            context['form']['template_count'] = str(request.POST['template_count'])
            request.session['template_count'] = context['form']['template_count']
        if 'max_cum_prob' in request.POST:
            context['form']['max_cum_prob'] = str(request.POST['max_cum_prob'])
            request.session['max_cum_prob'] = context['form']['max_cum_prob']
        if 'filter_threshold' in request.POST:
            context['form']['filter_threshold'] = str(request.POST['filter_threshold'])
            request.session['filter_threshold'] = context['form']['filter_threshold']

        smiles = resolve_smiles(smiles)
        if smiles is None:
            context['err'] = 'Could not parse!'
            return render(request, 'retro.html', context)

    if smiles is not None and not is_banned(request, smiles):

        # OLD: ALWAYS CHIRAL NOW
        # if 'retro_lit' in request.POST: return redirect('retro_lit_target', smiles=smiles)
        # if 'retro' in request.POST:
        #     return retro_target(request, smiles, chiral=False)
        # if 'retro_chiral' in request.POST:
        #     return retro_target(request, smiles, chiral=True)

        # Look up target
        smiles_img = reverse('draw_smiles', kwargs={'smiles': smiles})
        context['target'] = {
            'smiles': smiles,
            'img': smiles_img
        }

        # Perform retrosynthesis
        context['form']['smiles'] = smiles
        template_prioritization = context['form']['template_prioritization']
        precursor_prioritization = context['form']['precursor_prioritization']
        filter_threshold = context['form']['filter_threshold']

        try:
            template_count = int(context['form']['template_count'])
            if (template_count < 1):
                raise ValueError
        except ValueError:
            context['err'] = 'Invalid template count specified!'
            return render(request, 'retro.html', context)

        try:
            max_cum_prob = float(context['form']['max_cum_prob'])
            if (max_cum_prob <= 0):
                raise ValueError
        except ValueError:
            context['err'] = 'Invalid maximum cumulative probability specified!'
            return render(request, 'retro.html', context)

        try:
            filter_threshold = float(context['form']['filter_threshold'])
            filter_threshold = min(1, filter_threshold)
            filter_threshold = max(0, filter_threshold)
            apply_fast_filter = filter_threshold > 0
        except ValueError:
            context['err'] = 'Invalid filter threshold specified!'
            return render(request, 'retro.html', context)


        if template_prioritization == 'Popularity':
            template_count = 1e9

        print('Retro expansion conditions:')
        print(smiles)
        print(template_prioritization)
        print(precursor_prioritization)
        print(template_count)
        print(max_cum_prob)
        print(filter_threshold)

        startTime = time.time()
        res = get_top_precursors.delay(
            smiles, max_num_templates=template_count, max_cum_prob=max_cum_prob, 
            fast_filter_threshold=filter_threshold
        )
            
        (smiles, precursors) = res.get(300)
        # allow up to 5 minutes...can be pretty slow
        context['precursors'] = precursors
        context['footnote'] = RETRO_CHIRAL_FOOTNOTE
        context['time'] = '%0.3f' % (time.time() - startTime)

        # Change 'tform' field to be reaction SMARTS, not ObjectID from Mongo
        # Also add up total number of examples
        for (i, precursor) in enumerate(context['precursors']):
            context['precursors'][i]['tforms'] = \
                [dict(retro_transformer.lookup_id(_id), **{'id': str(_id)}) for _id in precursor['tforms']]
            context['precursors'][i]['mols'] = []
            # Overwrite num examples
            context['precursors'][i]['num_examples'] = sum(
                tform['count'] for tform in precursor['tforms'])
            for smiles in precursor['smiles_split']:
                ppg = pricer.lookup_smiles(smiles)
                context['precursors'][i]['mols'].append({
                    'smiles': smiles,
                    'ppg': '${}/g'.format(ppg) if ppg else 'cannot buy',
                })

    elif smiles is not None:
        context['err'] = 'Please don\'t waste our cycles on narcotics or weapons. That chemistry is well-studied. If you REALLY want this reaction, fork the askcos-core repo and edit the files in the /askcos/utilities/banned directory.'
    else:


        # Define suggestions
        context['suggestions'] = [
            {'name': 'Diphenhydramine', 'smiles': 'CN(C)CCOC(c1ccccc1)c2ccccc2'},
            {'name': 'Fluconazole', 'smiles': 'OC(Cn1cncn1)(Cn2cncn2)c3ccc(F)cc3F'},
            {'name': 'Nevirapine', 'smiles': 'Cc1ccnc2N(C3CC3)c4ncccc4C(=O)Nc12'},
            {'name': 'Atropine', 'smiles': 'CN1C2CCC1CC(C2)OC(=O)C(CO)c3ccccc3'},
            {'name': 'Diazepam', 'smiles': 'CN1C(=O)CN=C(c2ccccc2)c3cc(Cl)ccc13'},
        ]
        hidden = [{'name': 'Hydroxychloroquine', 'smiles': 'CCN(CCO)CCCC(C)Nc1ccnc2cc(Cl)ccc12'},
            {'name': 'Ibuprofen', 'smiles': 'CC(C)Cc1ccc(cc1)C(C)C(O)=O'},
            {'name': 'Tramadol', 'smiles': 'CN(C)C[C@H]1CCCC[C@@]1(C2=CC(=CC=C2)OC)O'},
            {'name': 'Lamivudine', 'smiles': 'NC1=NC(=O)N(C=C1)[C@@H]2CS[C@H](CO)O2'},
            {'name': 'Pregabalin', 'smiles': 'CC(C)C[C@H](CN)CC(O)=O'},
            {'name': 'Naproxen', 'smiles': 'COc1ccc2cc([C@H](C)C(=O)O)ccc2c1'},
            {'name': 'Imatinib', 'smiles': 'CN1CCN(CC1)Cc2ccc(cc2)C(=O)Nc3ccc(C)c(Nc4nccc(n4)c5cccnc5)c3'},
            {'name': 'Quinapril', 'smiles': 'CCOC(=O)[C@H](CCc1ccccc1)N[C@@H](C)C(=O)N2Cc3ccccc3C[C@H]2C(O)=O'},
            {'name': 'Atorvastatin', 'smiles': 'CC(C)c1n(CC[C@@H](O)C[C@@H](O)CC(O)=O)c(c2ccc(F)cc2)c(c3ccccc3)c1C(=O)Nc4ccccc4'},
            {'name': 'Bortezomib', 'smiles': 'CC(C)C[C@@H](NC(=O)[C@@H](Cc1ccccc1)NC(=O)c2cnccn2)B(O)O'},
            {'name': 'Itraconazole', 'smiles': 'CCC(C)N1N=CN(C1=O)c2ccc(cc2)N3CCN(CC3)c4ccc(OC[C@H]5CO[C@@](Cn6cncn6)(O5)c7ccc(Cl)cc7Cl)cc4'},
            {'name': '6-Carboxytetramethylrhodamine', 'smiles': 'CN(C)C1=CC2=C(C=C1)C(=C3C=CC(=[N+](C)C)C=C3O2)C4=C(C=CC(=C4)C(=O)[O-])C(=O)O'},
            {'name': '6-Carboxytetramethylrhodamine isomer', 'smiles': 'CN(C)c1ccc2c(c1)Oc1cc(N(C)C)ccc1C21OC(=O)c2ccc(C(=O)O)c1c2'},
            {'name': '(S)-Warfarin', 'smiles': 'CC(=O)C[C@@H](C1=CC=CC=C1)C2=C(C3=CC=CC=C3OC2=O)O'},
            {'name': 'Tranexamic Acid', 'smiles': 'NC[C@@H]1CC[C@H](CC1)C(O)=O'},
        ]

    context['footnote'] = RETRO_CHIRAL_FOOTNOTE
    return render(request, 'retro.html', context)

#@login_required
def retro_target(request, smiles):
    '''
    Given a target molecule, render page
    '''
    return retro(request, smiles=smiles)

def retro_network(request):
    context = {}
    
    enable_resolve = os.environ.get('ENABLE_SMILES_RESOLVER') == 'True'
    context['enableResolve'] = 'checked' if enable_resolve else ''

    return render(request, 'reaction_network.html', context)


@login_required
def retro_interactive_mcts(request, target=None):
    '''Builds an interactive retrosynthesis page'''

    context = {}
    context['warn'] = '<div style="text-align: center">If requests seem to take a long time, check the <a href="/status/" target="_blank">Server Status</a> page to see which resources are currently being used!</div>'

    context['max_depth_default'] = 4
    context['max_branching_default'] = 20
    context['retro_mincount_default'] = 0
    context['synth_mincount_default'] = 0
    context['expansion_time_default'] = 60
    context['max_ppg_default'] = 100
    context['template_count_default'] = 100
    context['template_prioritization'] = 'Relevance'
    context['max_cum_prob_default'] = 0.995
    context['precursor_prioritization'] = 'RelevanceHeuristic'
    context['forward_scorer'] = 'Template_Free'
    context['filter_threshold_default'] = 0.75
    context['template_prioritizer'] = 'reaxys'
    context['template_set'] = 'reaxys'

    if target is not None:
        context['target_mol'] = target

    if request.user.is_authenticated:
        context['logged_in'] = True
    else:
        context['logged_in'] = False

    return render(request, 'retro_interactive_mcts.html', context)


@ajax_error_wrapper
def ajax_start_retro_mcts_celery(request):
    '''Start builder'''
    data = {'err': False}

    run_async = json.loads(request.GET.get('async', 'true'))
    description = request.GET.get('description')

    smiles = request.GET.get('smiles', None)

    if is_banned(request, smiles):
        data['error'] = 'Hey are you really sure? It seems like you\'re fucking around, do you *need* to find out?'
        # return JsonResponse(data)

    max_depth = int(request.GET.get('max_depth', 4))
    max_branching = int(request.GET.get('max_branching', 25))
    expansion_time = int(request.GET.get('expansion_time', 60))
    max_ppg = int(request.GET.get('max_ppg', 10))
    template_count = int(request.GET.get('template_count', '100'))
    max_cum_prob = float(request.GET.get('max_cum_prob', '0.995'))
    chemical_property_logic = str(request.GET.get('chemical_property_logic', 'none'))
    max_chemprop_c = int(request.GET.get('max_chemprop_c', '0'))
    max_chemprop_n = int(request.GET.get('max_chemprop_n', '0'))
    max_chemprop_o = int(request.GET.get('max_chemprop_o', '0'))
    max_chemprop_h = int(request.GET.get('max_chemprop_h', '0'))
    chemical_popularity_logic = str(request.GET.get('chemical_popularity_logic', 'none'))
    min_chempop_reactants = int(request.GET.get('min_chempop_reactants', 5))
    min_chempop_products = int(request.GET.get('min_chempop_products', 5))
    filter_threshold = float(request.GET.get('filter_threshold', 0.75))
    apply_fast_filter = filter_threshold > 0
    template_prioritizer = request.GET.get('template_prioritizer', 'reaxys')
    template_set = request.GET.get('template_set', 'reaxys')
    return_first = json.loads(request.GET.get('return_first', 'false'))

    if request.user.is_authenticated:
        banned_reactions = list(set(
            [x.smiles for x in BlacklistedReactions.objects.filter(user=request.user, active=True)]))
        forbidden_molecules = list(set(
            [x.smiles for x in BlacklistedChemicals.objects.filter(user=request.user, active=True)]))
    else:
        banned_reactions = []
        forbidden_molecules = []

    default_val = 1e9 if chemical_property_logic == 'and' else 0
    max_natom_dict = defaultdict(lambda: default_val, {
        'logic': chemical_property_logic,
        'C': max_chemprop_c,
        'N': max_chemprop_n,
        'O': max_chemprop_o,
        'H': max_chemprop_h,
    })
    min_chemical_history_dict = {
        'logic': chemical_popularity_logic,
        'as_reactant': min_chempop_reactants,
        'as_product': min_chempop_products,
    }
    print('Tree building {} for user {} ({} forbidden reactions)'.format(
        smiles, request.user.id, len(banned_reactions)))
    print('Using chemical property logic: {}'.format(max_natom_dict))
    print('Using chemical popularity logic: {}'.format(min_chemical_history_dict))
    print('Returning as soon as any pathway found? {}'.format(return_first))

    historian_hashed = template_set == 'reaxys'

    res = get_buyable_paths_mcts.delay(smiles, max_branching=max_branching, max_depth=max_depth,
                                  max_ppg=max_ppg, expansion_time=expansion_time, max_trees=500,
                                  known_bad_reactions=banned_reactions,
                                  forbidden_molecules=forbidden_molecules,
                                  max_cum_template_prob=max_cum_prob, template_count=template_count,
                                  max_natom_dict=max_natom_dict, min_chemical_history_dict=min_chemical_history_dict,
                                  apply_fast_filter=apply_fast_filter, filter_threshold=filter_threshold,
                                  template_prioritizer=template_prioritizer, template_set=template_set,
                                  return_first=return_first, hashed=historian_hashed,
                                  run_async=run_async)

    if run_async:
        now = datetime.now()

        saved_result = SavedResults.objects.create(
            user=request.user,
            created=now,
            dt=now.strftime('%B %d, %Y %H:%M:%S %p'),
            result_id=res.id,
            result_state='pending',
            result_type='tree_builder',
            description=description
        )

        return JsonResponse({'id': res.id})
    else:
        (tree_status, trees) = res.get(expansion_time * 3)
        (num_chemicals, num_reactions, _) = tree_status
        data['html_stats'] = 'After expanding (with {} banned reactions, {} banned chemicals), {} total chemicals and {} total reactions'.format(
            len(banned_reactions), len(forbidden_molecules), num_chemicals, num_reactions)
        if trees:
            data['html_trees'] = render_to_string('trees_only.html',
                                                {'trees': trees, 'can_control_robot': can_control_robot(request)})
        else:
            data['html_trees'] = render_to_string('trees_none.html', {})

        # Save to session in case user wants to export
        request.session['last_retro_interactive'] = trees
        return JsonResponse(data)
