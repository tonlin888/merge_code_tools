#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys, json, os, datetime

GERRIT_SERVER = 'gerrit.fihtdc.com'
# regular expression start with ^
# status: open, merged
query = "status:" + "merged"
#query += " " + "branch:" + "^ZON/dev/.*/r0mp1V8.46.*/BSP"
query += " " + "branch:" + "OF6/dev/SDM660/302000080/PFAR"
#query += " " + "project:" + "^QC_19_21/platform/frameworks/base"
#query += " " + "owner:" + "	DanielYJHsieh"
#query += " " + "path:" + "^.*e2p.*"
#query += " " + "message:" + "modem"
query += " " + "after:" + "2021-03-29"
#query += " " + "before:" + "2020-2-18"

def main():
    cmd = "ssh -p 29418 " + GERRIT_SERVER + " -l tonycylin gerrit query --format=JSON --current-patch-set " + query + " > query.log"
    os.system(cmd)

    list_prjs = []
    f = open('query.log', 'r')
    lines = f.readlines()
    for line in lines:
        if "project" in line:
            j = json.loads(line)
            dt = datetime.datetime.utcfromtimestamp(j['lastUpdated'])
            dt = dt + datetime.timedelta(hours=8)
            #lastUpdated, project, branch, owner.name, currentPatchSet.revision, id, url, subject, commitMessage
            #print(j['project'], j['currentPatchSet']['revision'], dt.strftime("%m-%d %H:%M:%S"), j['owner']['name'], j['currentPatchSet']['revision'], j['subject'])
            print(j['project'], j['currentPatchSet']['revision'])
            list_prjs.append(j['project'][j['project'].index("/") + 1:])
    print('-----------------------')
    # all projects need to update
    print(' '.join(sorted(list(set(list_prjs)))))

if __name__ == '__main__':
    main()