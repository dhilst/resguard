#!/bin/bash
sed -ne '/"""/,/"""/p' reqguard.py | sed -e '/"""/d; s/^ \+//'
