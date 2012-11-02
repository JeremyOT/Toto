#!/bin/sh
# Starts and stops TOTO_PROCESS
#

case $1 in
start)
  
  TOTO_PROCESS --start

;;

stop)

  TOTO_PROCESS --stop

;;

restart)

  TOTO_PROCESS --restart

;;

*)

  echo "Usage: $0 {start|stop|restart}"
  echo
  echo "Make sure your Toto process is configured with absolute paths"
  echo "for all referenced files (PID, conf) before running the init.d script."
  exit 1

esac
