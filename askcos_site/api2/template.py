from bson.objectid import ObjectId
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from askcos_site.globals import retro_templates


class TemplateViewSet(ViewSet):
    """
    API endpoint for accessing template data.

    For a particular template, specified as URI parameter (`/api/v2/template/<template id>/`):

    Method: GET

    Returns:

    - `template`: reaction template

    ----------
    Export Reaxys query (`/api/v2/template/<template id>/export/`):

    Method: GET

    Returns:

    - JSON format Reaxys query

    ----------
    Query available template sets (`/api/v2/template/sets/`):

    Method: GET

    Returns:

    - `template_sets`: list of available template sets
    """

    def list(self, request):
        """Default behavior for GET request. Not supported."""
        return Response({'detail': 'Template list view not supported.'}, status=405)

    def retrieve(self, request, pk):
        """Return single template entry by mongo _id."""
        resp = {'error': None, 'template': None}

        transform = retro_templates.find_one({'_id': pk})
        if not transform:
            try:
                transform = retro_templates.find_one({'_id': ObjectId(pk)})
            except:
                transform = None

        if not transform:
            resp['error'] = 'Cannot find template with id {0}'.format(pk)
            return Response(resp)

        transform['_id'] = pk
        transform.pop('product_smiles', None)
        transform.pop('name', None)
        if transform.get('template_set') == 'reaxys':
            refs = transform.pop('references', [''])
            transform['references'] = [x.split('-')[0] for x in refs]

        resp['template'] = transform

        return Response(resp)

    @action(detail=False, methods=['GET'])
    def sets(self, request):
        """Returns available template sets that exist in mongodb"""
        resp = {'template_sets': retro_templates.distinct('template_set')}
        return Response(resp)

    @action(detail=True, methods=['GET'])
    def export(self, request, pk):
        """Return single template entry by mongo _id as a reaxys query."""
        resp = {}

        transform = retro_templates.find_one({'_id': pk})
        if not transform:
            try:
                transform = retro_templates.find_one({'_id': ObjectId(pk)})
            except:
                transform = None

        if not transform:
            resp['error'] = 'Cannot find template with id {0}'.format(pk)
            return Response(resp)

        if transform.get('template_set') != 'reaxys':
            resp['error'] = 'Template is not in the reaxys template set'
            return Response(resp)

        references = '; '.join([ref.split('-')[0] for ref in transform['references']])
        resp['fileName'] = 'reaxys_query.json'
        resp['version'] = '1.0'
        resp['content'] = {
            'id': 'root',
            'facts': [{
                'id': 'Reaxys487',
                'fields': [{
                    'value': references,
                    'boundOperator': 'op_num_equal',
                    'id': 'RX.ID',
                    'displayName': 'Reaction ID'
                }],
                'fieldsLogicOperator': 'AND',
                'exist': False,
                'bio': False
            }]
        }
        resp['exist'] = False
        resp['bio'] = False
        resp['content']['facts'][0].pop('logicOperator', None)

        return Response(resp)
