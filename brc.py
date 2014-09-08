service = 'blogger'
service_options = {
  'blog': 6425054342484936402,
}
handlers = {
  'Markdown': {
    'options': {
      'embed_images': True,
      'config': {
        'extensions': ['codehilite', 'footnotes', 'tables', 'toc'],
        'extension_configs' : {
            'codehilite' : [ ('noclasses', 'True') ]
                    }
      },
    },
  },
}
