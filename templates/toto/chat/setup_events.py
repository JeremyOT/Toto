
def print_event(args):
  print "Event: ", args

def invoke(event_manager):
  print event_manager
  event_manager.register_handler('message', print_event, persist=True)
