var container = document.getElementsByClassName('container')[0];
container.style.width=null;

showLoader();

function hideNetwork(n) {
  var networkDiv = document.querySelectorAll('.tree-graph')[n];
  var hideDiv = document.querySelectorAll('.hideNetwork')[n];
  var showDiv = document.querySelectorAll('.showNetwork')[n];
  networkDiv.style.display = 'none';
  hideDiv.style.display = 'none';
  showDiv.style.display = '';
}

function hideAllNetworks() {
  for (var n=0; n<document.querySelectorAll('.tree-graph').length; n++) {
    hideNetwork(n)
  }
}

function showNetwork(n) {
  var networkDiv = document.querySelectorAll('.tree-graph')[n];
  var hideDiv = document.querySelectorAll('.hideNetwork')[n];
  var showDiv = document.querySelectorAll('.showNetwork')[n];
  networkDiv.style.display = '';
  hideDiv.style.display = '';
  showDiv.style.display = 'none';
}

function showAllNetworks() {
  for (var n=0; n<document.querySelectorAll('.tree-graph').length; n++) {
    showNetwork(n)
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function colorOf(child) {
  if (child['ppg']) {
    if (child['as_reactant'] || child['as_product']) {
      return "#1B5E20" // green
    }
    else {
      return '#FFC400' // yellow
    }
  }
  else {
    if (child['as_reactant'] || child['as_product']) {
      return  '#E65100' // orange
    }
    else {
      return '#B71C1C' // red
    }
  }
}

function makeNode(child, id) {
  var node = {};
  if (child['is_chemical']) {
    node['id'] = id
    node['ppg'] = child['ppg']
    node['smiles'] = child['smiles']
    node['image'] = "/api/v2/draw/?smiles="+encodeURIComponent(child['smiles'])
    node['shape'] = "image"
    node['type'] = 'chemical'
    var buyableString = (Number(child['ppg'])) ? '$'+child['ppg']+'/g' : 'not buyable'
    node['as_reactant'] = child['as_reactant']
    node['as_product'] = child['as_product']
    node['title'] = `${child['smiles']}<br>
    ${child['as_reactant']} precedents as reactant<br>
    ${child['as_product']} precedents as product<br>
    ${buyableString}`
    node['borderWidth'] = 2
    node['color'] = {
      border: colorOf(child)
    }
  }
  else if (child['is_reaction']) {
    node['type'] = 'reaction'
    node['id'] = id
    node['necessary_reagent'] = child['necessary_reagent']
    node['num_examples'] = child['num_examples']
    node['plausibility'] = child['plausibility']
    node['smiles'] = child['smiles']
    node['template_score'] = child['template_score']
    node['tforms'] = child['tforms']
    node['label'] = `${child['num_examples']} examples
FF score: ${Number(child['plausibility']).toFixed(3)}
Template score: ${Number(child['template_score']).toFixed(3)}`
    node['font'] = {align: 'center'}
  }
  return node
}

function makeTreeData(obj, parent, nodes, edges) {
  var node = makeNode(obj, nodes.length);
  nodes.add(node);
  if (parent != 0) {
    edges.add({
      from: parent.id,
      to: node.id,
      length: 0
    })
  }
  for (child of obj.children) {
    makeTreeData(child, node, nodes, edges);
  }
}

function makeNodes(children, root) {
  var nodes = [];
  var edges = [];
  var childrenOfChildren = [];
  for (child of children) {
    nodes.push(makeNode(child))
    edges.push({
      from: root.id,
      to: child.id
    })
    childrenOfChildren.push(child.children)
  }
  var result = {
    nodes: nodes,
    edges: edges,
    children: childrenOfChildren
  }
  return result
}

function treeStats(tree) {
    let nodes = new vis.DataSet([])
    let edges = new vis.DataSet([])
    makeTreeData(tree, 0, nodes, edges)
    let numReactions = 0
    let avgScore = 0
    let avgPlausibility = 0
    let minScore = 1.0
    let minPlausibility = 1.0
    for (node of nodes.get()) {
        if (node.type == 'reaction') {
            numReactions += 1
            avgScore += node.template_score
            avgPlausibility += node.plausibility
            minScore = Math.min(minScore, node.template_score)
            minPlausibility = Math.min(minPlausibility, node.plausibility)
        }
    }
    avgScore /= numReactions
    avgPlausibility /= numReactions

    tree.numReactions = numReactions
    tree.firstStepScore=  nodes.get(1).template_score
    tree.avgScore = avgScore
    tree.avgPlausibility = avgPlausibility
    tree.minPlausibility = minPlausibility
}

function sortObjectArray(arr, prop, reverse) {
    arr.sort(function(a, b) {
        if (!!reverse) {
            return a[prop] - b[prop]
        }
        else {
            return b[prop] - a[prop]
        }
    })
}

function initializeNetwork(data, elementDiv) {
    var container = elementDiv;
    var options = {
        nodes: {
            color: {
                border: '#000000',
                background: '#FFFFFF'
            },
            shapeProperties: {
                useBorderWithImage: true,
                useImageSize: true
            }
        },
        edges: {
            length: 1
        },
        interaction: {
            multiselect: false,
            hover: true,
            dragNodes: false,
            // dragView: false,
            selectConnectedEdges: false,
            tooltipDelay: 0,
            // zoomView: false
        },
        layout: {
          hierarchical: {
            levelSeparation: 150,
            nodeSpacing: 175,
          }
        },
        physics: false
    };
    network = new vis.Network(container, data, options);
    network.on("beforeDrawing",  function(ctx) {
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height)
        ctx.restore();
    })
    return network
}

var csrftoken = getCookie('csrftoken');

var app = new Vue({
    el: '#app',
    data: {
      resultId: "",
      numChemicals: 0,
      numReactions: 0,
      trees: [],
      settings: {},
      showSettings: false,
      selected: null,
      currentTreeId: 0,
      networkData: {},
      treeSortOption: 'numReactions'
    },
    mounted: function() {
      this.resultId = this.$el.getAttribute('data-id');
      this.getResult(this.resultId);
    },
    methods: {
      getResult: function(id) {
        showLoader();
        fetch('/api/get-result/?id='+id)
          .then(resp => resp.json())
          .then(json => {
            var result = json['result'];
            var stats = result['result']['status'];
            var trees = result['result']['paths'];
            this.numChemicals = stats[0];
            this.numReactions = stats[1];
            this.trees = trees;
            this.settings = result['settings'];
            this.networkContainer = document.getElementById('left-pane')
            if (this.trees.length) {
                this.allTreeStats()
                this.sortTrees(this.treeSortOption, true)
                this.buildTree(this.currentTreeId, this.networkContainer);
            }
            hideLoader()
          })
      },
      buildTree: function(treeId, elem) {
        var nodes = new vis.DataSet([]);
        var edges = new vis.DataSet([]);
        makeTreeData(this.trees[treeId], 0, nodes, edges);
        this.networkData = {
          nodes: nodes,
          edges: edges
        }
        this.network = initializeNetwork(this.networkData, elem);
        this.network.on('selectNode', function(params) {
          app.showNode(params.nodes[0])
        });
        sleep(500).then(() => app.network.fit())
      },
      sortTrees: function(prop, reverse) {
        sortObjectArray(this.trees, prop, reverse)
        this.currentTreeId = 0
        this.buildTree(this.currentTreeId, this.networkContainer)
      },
      nextTree: function() {
          if (this.currentTreeId < this.trees.length - 1) {
              this.selected = null
              this.currentTreeId =  this.currentTreeId + 1
              this.buildTree(this.currentTreeId, this.networkContainer)
          }
      },
      prevTree: function() {
          if (this.currentTreeId > 0) {
              this.selected = null
              this.currentTreeId =  this.currentTreeId - 1
              this.buildTree(this.currentTreeId, this.networkContainer)
          }
      },
      firstTree: function() {
        this.selected = null
        this.currentTreeId = 0
        this.buildTree(this.currentTreeId, this.networkContainer)
      },
      lastTree: function() {
        this.selected = null
        this.currentTreeId = this.trees.length-1
        this.buildTree(this.currentTreeId, this.networkContainer)
      },
      allTreeStats: function() {
        this.treeStats = []
        for (tree of this.trees) {
          this.treeStats.push(treeStats(tree))
        }
      },
      banItem: function() {
        var nodeId = this.network.getSelectedNodes();
        if (!nodeId.length) { return }
        var desc = prompt("Please enter a reason (for your records only)", "no reason");
        var node = this.networkData.nodes.get(nodeId[0]);
        if (node['type'] === 'chemical') {
            var url =  '/api/v2/banlist/chemicals/'
            var speciesName = 'chemical'
        }
        else {
            var url = '/api/v2/banlist/reactions/'
            var speciesName = 'reaction'
        }
        const body = {
            smiles: node.smiles,
            description: desc,
        };
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify(body)
        })
            .then(resp => resp.json())
            .then(json => {
                const datetime = dayjs(json.created).format('MMMM D, YYYY h:mm A');
                alert(`Banned ${speciesName} ${node.smiles} at ${datetime}`)
            });
      },
      showNode: function(nodeId) {
        var node = this.networkData.nodes.get(nodeId)
        this.selected = node
        if (node.type=='chemical' && !!!node.source) {
            fetch('/api/v2/buyables/?q='+encodeURIComponent(node.smiles))
                .then(resp => resp.json())
                .then(json => {
                    if (json.result.length) {
                        this.networkData.nodes.update({id: node.id, source: json.result[0].source})
                        this.$set(this.selected, 'source', json.result[0].source)
                    }
                })
        }
      }
    },
    delimiters: ['%%', '%%'],
});
