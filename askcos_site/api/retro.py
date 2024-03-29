from celery.exceptions import TimeoutError
from django.http import JsonResponse
from rdkit import Chem

from askcos_site.askcos_celery.treebuilder.tb_c_worker import get_top_precursors
from askcos_site.main.utils import is_banned

TIMEOUT = 120


def singlestep(request):
    resp = {}
    resp['request'] = dict(**request.GET)
    run_async = request.GET.get('async', False)
    target = request.GET.get('target')

    if is_banned(request, target):
        resp['error'] = 'Please don\'t waste our cycles on narcotics or weapons. That chemistry is well-studied. If you REALLY want this reaction, fork the askcos-core repo and edit the files in the /askcos/utilities/banned directory.'
        # return JsonResponse(resp, status=400)

    max_num_templates = int(request.GET.get('num_templates', 100))
    max_cum_prob = float(request.GET.get('max_cum_prob', 0.995))
    fast_filter_threshold = float(request.GET.get('filter_threshold', 0.75))
    template_set = request.GET.get('template_set', 'reaxys')
    template_prioritizer = request.GET.get('template_prioritizer', 'reaxys')

    if not target:
        resp['error'] = 'Required parameter "target" missing'
        return JsonResponse(resp, status=400)

    mol = Chem.MolFromSmiles(target)
    if not mol:
        resp['error'] = 'Cannot parse target smiles with rdkit'
        return JsonResponse(resp, status=400)
    
    cluster = request.GET.get('cluster', 'True') in ['True', 'true']
    cluster_method = request.GET.get('cluster_method', 'kmeans')
    cluster_feature = request.GET.get('cluster_feature', 'original')
    cluster_fp_type = request.GET.get('cluster_fp_type', 'morgan')
    cluster_fp_length = int(request.GET.get('cluster_fp_length', 512))
    cluster_fp_radius = int(request.GET.get('cluster_fp_radius', 1))

    selec_check = request.GET.get('allow_selec', 'True') in ['True', 'true']

    res = get_top_precursors.delay(
        target,
        template_set=template_set,
        template_prioritizer=template_prioritizer,
        fast_filter_threshold=fast_filter_threshold,
        max_cum_prob=max_cum_prob,
        max_num_templates=max_num_templates,
        cluster=cluster,
        cluster_method=cluster_method,
        cluster_feature=cluster_feature,
        cluster_fp_type=cluster_fp_type,
        cluster_fp_length=cluster_fp_length,
        cluster_fp_radius=cluster_fp_radius,
        selec_check=selec_check,
    )

    if run_async:
        resp['id'] = res.id
        resp['state'] = res.state
        return JsonResponse(resp)

    try:
        (smiles, precursors) = res.get(TIMEOUT)
    except TimeoutError:
        resp['error'] = 'API request timed out (limit {}s)'.format(TIMEOUT)
        res.revoke()
        return JsonResponse(resp, status=408)
    except Exception as e:
        resp['error'] = str(e)
        res.revoke()
        return JsonResponse(resp, status=400)

    resp['precursors'] = precursors
    for precursor in precursors:
        precursor['templates'] = precursor.pop('tforms')
    return JsonResponse(resp)
