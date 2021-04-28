#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys, re, os, time, getopt, subprocess
import xml.etree.ElementTree as ET

# some information no need to change every time
TOOL_VERSION = '3.1'
ACCOUNT = 'TonyCYLin'
EMAIL = ACCOUNT + '@fih-foxconn.com'
ANDROID_VER = 'PFAR' # pattern for finding merge branch. upstream="[project]/.../[ANDROID_VER]"

# global const variable
PRJ_NAME = 0
PRJ_REV = 1
PRJ_UPSTREAM = 2
PRJ_PATH = 3
PRJ_REMOTE = 4
TAB = '  '

# global variable
_merge_branch = _code_branch = _working_branch = _gerrit_server = ''
#_gerrit_server = 'gerrit3.fihtdc.com'
#_merge_branch = 'ZON/dev/EXTERNAL/MT6761/r0mp1V6.7.1/PFAR' # current developing branch
#_code_branch = 'ZON/dev/EXTERNAL/MT6761/r0mp1V8.46/PFAR' # new developing branch
#_merge_branch = 'ZON/dev/MT6761/r0mp1V6.7.1/PFAR'
#_code_branch = 'ZON/dev/MT6761/r0mp1V8.46/PFAR'

_project = ''
_remote_info = {}
_default_remote = ''

_working_path = os.getcwd()
all_log = open(os.path.join(_working_path, 'merge_' + time.strftime('%Y%m%d') + '.log'), 'a')
conflict_log = open(os.path.join(_working_path, 'conflict_' + time.strftime('%Y%m%d') + '.log'), 'a')
_file_loc = ''

def show_usage():
    print ('Usage:');
    print ('       1. repo sync new version code base')
    print ('       2. Copy daily build manifest XML to the root folder of code')
    print ('       3. Copy gitAutoMerge.py to the root folder of code')
    print ('       4. Merge code: python3 gitAutoMerge.py daily.xml (ex.20200222_OG6_Q_2000037_Daily.xml)')
    print ('       5. Fix conflict by check conflict*.log, and commit git project after conflict fixed')
    print ('       7. Push code: python3 gitAutoMerge.py -p daily.xml')
    print ('------------------------------------------------------------------')
    print ('Command: gitAutoMerge [-p|-m|-c|-k file|-t file] yyyymmdd_prj_v_revision_Daily.xml')
    print ('       -m, --merge              : merge git projects')
    print ('       -p, --push               : push merged git projects')
    print ('       -c, --check              : check merge state')
    print ('       -k, --chery-pick [file]  : chery pick from file')
    print ('                                  file format: Git_Project Commit_ID');
    print ('                                  ex: platform/packages/apps/Settings 848b19087804e99282af5693a6a7f95809108993');
    print ('       -t, --muti-push [file]   : push git project from file')
    print ('                                  file format: Git_Project Commit_ID');
    print ('------------------------------------------------------------------')
    print ('    (yyyymmdd_prj_v_revision_Daily.xml, will get project code from filename by this format)')

def show_info(operation, xml_file, cherry_pick_file):
    localtime = time.asctime(time.localtime(time.time()) )
    print ('******************integration info****************** ver.' + TOOL_VERSION + ", " + localtime)
    print ('Merge from         : ' + _merge_branch + ' at ' + xml_file)
    print ('Merge into         : ' + _code_branch)
    print ('Working branch     : ' + _working_branch)
    print ('Account            : ' + ACCOUNT)
    print ('GerritServer       : ' + _gerrit_server)
    print ('Operation          : ' + operation)
    if cherry_pick_file:
        print ('Cherry Pick        : ' + cherry_pick_file)
    print ('********************************************************')
    print ('rember commit each git project after conflict fixed')
    log('-------------------------------------- ' + localtime + ' --------------------------------------')

def push_prj(prjs):
    for prj in prjs:
        is_good = True
        has_change = False
        no_need_push = False
        path = os.path.join(_working_path, prj[PRJ_PATH])
        tag = '[' + str(prjs.index(prj) + 1) + '/' + str(len(prjs)) + '] ' + prj[PRJ_NAME] + ', ' + prj[PRJ_PATH]
        if os.path.isdir(path):
            log('\n---> push: ' + tag)
            os.chdir(path)
            result = doCmd('git status')
            log('\t---')
            if not 'working tree clean' in result: is_good = False
            if 'Your branch is up to date' in result:
                no_need_push = True
            else:
                cmd = 'git push ssh://' + ACCOUNT + '@' + _gerrit_server + ':29418/' + _remote_info[prj[PRJ_REMOTE]] + '/'
                cmd += prj[PRJ_NAME] + ' HEAD:refs/for/' + _code_branch
                result = doCmd(cmd)
                if not 'no new changes' in result: has_change = True
        else:
            is_good = False
            log(TAB + '[ERROR]: ' + prj[PRJ_PATH] + ' not exist')
        if not is_good: tag = 'ERROR ' + tag
        if has_change: tag = 'CHANGE ' + tag
        if no_need_push: tag = 'NO_PUSH ' + tag
        log('<--- push: ' + tag)

def merge_prj(prjs):
    for prj in prjs:
        path = os.path.join(_working_path, prj[PRJ_PATH])
        tag = '[' + str(prjs.index(prj) + 1) + '/' + str(len(prjs)) + '] ' + prj[PRJ_NAME] + ', ' + prj[PRJ_PATH] + ', ' + prj[PRJ_REV]
        is_good = True
        log('\n---> merge: ' + tag)
        if os.path.isdir(path):
            os.chdir(path)

            # whether code_branch contain this patch
            result = doCmd('git checkout ' + _code_branch)
            if 'did not match any file(s) known to git' in result:
                log('<--- merge: ERROR ' + _code_branch + ' not exist. ' + tag)
                continue

            # whether code_branch contain unmerged file
            if 'you need to resolve your current index first' in result:
                log('<--- merge: ' + '[ERROR]: ' + _code_branch + ' need to resolve conflict file first. ' + tag)
                continue

            result = doCmd('git branch --contains ' + prj[PRJ_REV])

            if _code_branch not in result:
                doCmd('git config user.name ' + ACCOUNT + ' && git config user.email ' + EMAIL)

                result = doCmd('git fetch ' + prj[PRJ_REMOTE] + ' --unshallow')
                # try again when git fetch failure
                if 'error: remote did not send all necessary objects' in result:
                    doCmd('git fetch ' + prj[PRJ_REMOTE] + ' --unshallow')
                doCmd('git fetch ' + prj[PRJ_REMOTE] )

                log(TAB + TAB + '----------')
                doCmd('git branch ' + _working_branch + ' ' + prj[PRJ_REV])
                log(TAB + TAB + '----------')
                doCmd('git branch -v')
                log(TAB + TAB + '----------')
                is_good = doMerge(prj)
            else:
                log(TAB + prj[PRJ_REV] + ' already in ' + _code_branch + '\n' + TAB + '###### no need to merge ######')
            if not is_good: tag = 'CONFLICT ' + tag
            log('<--- merge: ' + tag)
        else:
            log('<--- merge: ' + 'ERROR: folder not exist (' + prj[PRJ_PATH] + ')' + tag)

def check_prj(prjs):
    for prj in prjs:
        path = os.path.join(_working_path, prj[PRJ_PATH])
        tag = '[' + str(prjs.index(prj) + 1) + '/' + str(len(prjs)) + '] ' + prj[PRJ_NAME] + ', ' + prj[PRJ_PATH] + ', ' + prj[PRJ_REV]
        log('\n---> check: ' + tag)
        if os.path.isdir(path):
            os.chdir(path)

            # whether code_branch contain this patch
            result = doCmd('git checkout ' + _code_branch)
            if 'did not match any file(s) known to git' in result:
                log(TAB + '[ERROR]: ' + _code_branch + ' not exist')
                log('<--- check: ' + tag)
                continue

            # whether code_branch contain unmerged file
            if 'you need to resolve your current index first' in result:
                log(TAB + '[ERROR]: ' + _code_branch + ' need to resolve conflict file first')
                log('<--- check: ' + tag)
                continue

            result = doCmd('git branch --contains ' + prj[PRJ_REV])

            if _code_branch not in result:
                log(TAB + prj[PRJ_REV] + ' not in ' + _code_branch + '\n' + TAB + '$$$$$$ need to merge $$$$$$')
            else:
                log(TAB + prj[PRJ_REV] + ' already in ' + _code_branch + '\n' + TAB + '###### no need to merge ######')
        else:
            log(TAB + '[ERROR]: folder not exist (' + prj[PRJ_PATH] + ')')
        log('<--- check: ' + tag)

def cherry_pick(prjs, cherry_pick_file):
    f = open(cherry_pick_file, 'r')
    lines = f.readlines()
    lines.reverse()

    for line in lines:
        tag = '[' + str(lines.index(line) + 1) + '/' + str(len(lines)) + '] ' + line.split()[0] + ', ' + line.split()[1]
        log('\n---> cherry-pick: ' + tag)
        found = False
        for prj in prjs:
            if line.split()[0] in prj[PRJ_NAME]:
                found = True
                path = os.path.join(_working_path, prj[PRJ_PATH])
                if os.path.isdir(path):
                    os.chdir(path)
                    doCmd('git checkout ' + _code_branch)
                    doCmd('git config user.name ' + ACCOUNT + ' && git config user.email ' + EMAIL)
                    doCmd('git fetch ' + prj[PRJ_REMOTE])
                    log(TAB + TAB + '----------')
                    doCmd('git cherry-pick ' + line.split()[1])
                    doCmd('git branch -v')
                else:
                    log(TAB + '[ERROR]: folder not exist (' + path + ')')
        if not found:
            log(TAB + '[Error] Can not find ' + line.split()[0] + ' at target projects ###')
        log('<--- cherry-pick: ' + tag)

def multi_push(prjs, cherry_pick_file):
    f = open(cherry_pick_file, 'r')
    lines = f.readlines()
    # remove space, new line...
    lines = [i.strip() for i in lines]
    # remove duplicate git project
    lines = sorted(set(lines), key = lines.index)

    for line in lines:
        tag = '[' + str(lines.index(line) + 1) + '/' + str(len(lines)) + '] ' + line.split()[0]
        log('\n---> multi-push: ' + tag)
        found = False
        for prj in prjs:
            if line.split()[0] in prj[PRJ_NAME]:
                found = True
                path = os.path.join(_working_path, prj[PRJ_PATH])
                if os.path.isdir(path):
                    os.chdir(path)
                    cmd = 'git push ssh://' + ACCOUNT + '@' + _gerrit_server + ':29418/' + _remote_info[prj[PRJ_REMOTE]] + '/'
                    cmd += prj[PRJ_NAME] + ' HEAD:refs/for/' + _code_branch
                    doCmd(cmd)
                else:
                    log(TAB + '[ERROR]: folder not exist (' + path + ')')
        if not found:
            log(TAB + '[Error] Can not find ' + line.split()[0] + ' at target projects ###')
        log('<--- multi-push: ' + tag)

# -----------------------------------------------------------------------------------
def filter_prj(xml_file):
    global _remote_info, _merge_branch, _default_remote

    tree = ET.parse(xml_file)
    root = tree.getroot()

    # try to find merge branch from daily build xml
    if not _merge_branch:
        for child in root.findall('project') + root.findall('reset-project'):
            upstream = child.attrib.get('upstream')
            if upstream.endswith(ANDROID_VER):
                _merge_branch = upstream
                break

    if not _merge_branch:
        print('Can not read merge branch from ' + xml_file)
        sys.exit(2)

    for child in root.findall('remote'):
        name = child.attrib.get('name')
        fetch = child.attrib.get('fetch')
        if fetch == '.': fetch = 'QC'
        elif fetch.startswith('../'): fetch = fetch[3:]
        _remote_info[name] = fetch

    projs = []
    for child in root.findall('project') + root.findall('reset-project'):
        get_value = lambda val, default: default if not val else val
        name = child.attrib.get('name')
        path = get_value(child.attrib.get('path'), name)
        remote = get_value(child.attrib.get('remote'), _default_remote)
        rev = child.attrib.get('revision')
        upstream = get_value(child.attrib.get('upstream'), rev)
        if upstream == _merge_branch: projs.append([name, rev, upstream, path, remote])

    return projs

def log(s):
    all_log.write(s + '\n')
    all_log.flush()
    print(str(s))

def doCmd(cmd):
    log(TAB + cmd)
    ret = ''
    tmp_log = os.path.join(_working_path, 'tmp.log')
    os.system(cmd + " 2>&1 | tee " + tmp_log)
    f = open(tmp_log, 'r')
    for line in f.readlines():
        log(TAB + line.strip())
        ret += TAB + line
    return ret

def generate_link(prj, line, branch):
    l = 'http://' + _gerrit_server + ':7474/gitweb/?p='
    l += _remote_info[prj[PRJ_REMOTE]] + '/' + prj[PRJ_NAME] + '.git' + ';'
    l += 'f=' + line[line.find('Merge conflict') + 18:] + ';'
    l += 'hb=refs/heads/' + branch + ';'
    l += 'a=blame' # shortlog, blob_plain
    return l

def doMerge(prj):
    cmd = 'git merge --no-ff ' + _working_branch
    log(TAB + cmd)
    c_lines = []
    is_good = True

    # output merge result to tmp.log
    tmp_log = os.path.join(_working_path, 'tmp.log')
    os.system(cmd + " 2>&1 | tee " + tmp_log)
    f = open(tmp_log, 'r')
    for line in f.readlines():
        line = line.strip()
        if 'Your local changes to the following files would be overwritten by merge' in line:
            is_good = False
            log(TAB + '[ERROR]: ' + line)
        else:
            log(TAB + line.strip())
        if 'CONFLICT' in line: c_lines.append(line)
        if 'Automatic merge failed' in line: is_good = False
        if 'not something we can merge' in line: is_good = False

    # keep conflict file list at conflict*.log
    if c_lines:
        conflict_log.write('--->' + prj[PRJ_NAME] + '\n')
        for line in c_lines:
            line = line.strip()
            k = line.find('Merge conflict')
            l = line[:k] + _file_loc + '/' + prj[PRJ_PATH] + '/' + line[k + 18:]
            conflict_log.write(l + '\n')
            conflict_log.write('\t\t\t\t\t' + generate_link(prj, line, _merge_branch) + '\n')
        conflict_log.write('<---' + prj[PRJ_NAME] + '\n\n')
        conflict_log.flush()
    return is_good

def collect_info(xml):
    global _code_branch, _project, _merge_branch, _gerrit_server, _working_branch, _default_remote, _file_loc
    merge_projects = []

    # try to find project code from daily build xml, ex: 20200222_OG6_Q_2000037_Daily.xml -> OG6
    if len(xml) > 12 and 'Daily.xml' in xml: _project = xml[9:12]
    if not _working_branch: _working_branch = 'rel/ORI/' + xml[:-10]

    root = ET.parse('.repo/manifest.xml').getroot()

    _default_remote = root.find('default').attrib.get('remote')

    # find gerrit server
    if not _gerrit_server:
        for child in root.findall('remote'):
            if child.attrib.get('name') == _default_remote:
                # http://gerrit3.fihtdc.com/ --> gerrit3.fihtdc.com
                _gerrit_server = child.attrib.get('review')[7:-1]

    # collect projects need to merged
    merge_projects = filter_prj(xml)

    # find the new branch
    if not _code_branch:
        for child in root.findall('include'):
            if ANDROID_VER + '.xml' in child.attrib.get('name'):
                upper_xml = child.attrib.get('name')
                break
        root = ET.parse('.repo/manifests/' + upper_xml).getroot()
        for child in root.findall('reset-project'):
            rev = child.attrib.get('revision')
            if rev.endswith(ANDROID_VER):
                _code_branch = rev
                break

    # find source file location, /media/Workspace/tony/zon846 -> file://10.57.61.113/Workspace/tony/zon846
    p = subprocess.Popen('hostname -I', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    machine_ip = p.stdout.readline().strip().decode('utf-8')
    _file_loc = 'file://' + machine_ip + '/' + os.getcwd()[os.getcwd().find('/', 1) + 1:]

    # project, merge_branch, code_branch must not be empty
    if not _project or not _merge_branch or not _code_branch:
        print('Can not find import information.')
        print('Please check xml file name and .repo folder!')
        sys.exit(2)

    return merge_projects
# --------------------------------------------------------------------------

def main(argv):
    global _working_branch, _project
    operation = 'merge'

    try:
        opts, args = getopt.getopt(argv,'mpck:t:',['merge','push','check','cherry-pick=', 'multi-push'])
    except getopt.GetoptError:
      show_usage()
      sys.exit(2)

    cherry_pick_file = ''
    for opt, arg in opts:
        if opt in ('-p', '--push'): operation = 'push'
        if opt in ('-m', '--merge'): operation = 'merge'
        if opt in ('-c', '--check'): operation = 'check'
        if opt in ('-k', '--cherry-pick'):
            operation = 'cherry-pick'
            cherry_pick_file = arg
        if opt in ('-t', '--multi-push'):
            operation = 'multi-push'
            cherry_pick_file = arg

    if args: xml_file = args[0]
    if not xml_file: show_usage()

    # list git project need merge
    target_prjs = collect_info(xml_file)
    show_info(operation, xml_file, cherry_pick_file)

    ans = input('is everythings good? (y/N)')
    if ans.lower() == 'y':
        if operation == 'merge': merge_prj(target_prjs)
        elif operation == 'push': push_prj(target_prjs)
        elif operation == 'check': check_prj(target_prjs)
        elif operation == 'cherry-pick': cherry_pick(target_prjs, cherry_pick_file)
        elif operation == 'multi-push': multi_push(target_prjs, cherry_pick_file)
    else:
        return

if __name__ == '__main__':
    main(sys.argv[1:])