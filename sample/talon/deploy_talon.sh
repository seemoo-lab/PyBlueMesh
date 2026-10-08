#!/bin/bash
# ------------------------------------------------------------------
# @Author: Daniel Steinmetzer
# @Date:   2018-07-12
# @Last Modified by:   Daniel Steinmetzer
# @Last Modified time: 2018-07-17
# ------------------------------------------------------------------

USAGE="Usage: deploy_talon.sh device"

# --- Options processing -------------------------------------------
if [ $# == 0 ] ; then
    echo $USAGE
    exit 1;
fi

device=$1

CFGFILE='talon.conf'
MODULE_PATH=modules
SCP='scp -o StrictHostKeyChecking=no'
SSH='ssh -o StrictHostKeyChecking=no'

# -- Body ---------------------------------------------------------

echo Deploying TPyNode to Talon Device at $device ...
$SCP $CFGFILE root@$device:/etc/tpynode.conf
$SSH root@$device 'rm -rf /var/tpymodules/' 
$SCP -r $MODULE_PATH root@$device:/var/tpymodules/


# -----------------------------------------------------------------