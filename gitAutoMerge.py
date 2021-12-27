#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 2021/11/23@Tony
import argparse
import json
import os
import platform
import re
import time
import xml.etree.ElementTree as ElementTree

# some information no need to change every time
__tool_version__ = "3.2"
__account__ = "TonyCYLin"
__email__ = f"{__account__}@fih-foxconn.com"
__git_auto_merge_last_settings__ = ".gitAutoMergeSettings"

from json import JSONDecodeError
from subprocess import Popen, PIPE, STDOUT


class Utils:
    tab = "    "

    def __init__(self, root):
        self.root = root

    @staticmethod
    def choice(title, options):
        options.sort()
        if not options:
            raise BaseException("no options")
        elif len(options) == 1:
            return options[0]
        for i, option in enumerate(options):
            print(f"{i}: {option}")
        while True:
            val = input(f"{title} is ? ")
            if 0 <= int(val) < len(options):
                return options[int(val)]

    # merge.log and conflict.log
    def log(self, txt, merge_mode=True, color=False):
        name = "merge" if merge_mode else "conflict"
        output = os.path.join(self.root, name + "_" + time.strftime('%Y%m%d') + ".log")
        lines = txt.split("\n") if type(txt) == str else txt
        with open(output, "a") as f:
            for line in lines:                
                f.write(line + "\n")
                line = "\033[7m" + line + "\033[0m"if color else line
                print(line) if merge_mode else None
    
    @staticmethod
    def run(cmd):
        process = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
        process.wait()
        result = [s.decode('utf-8') for s in process.stdout.readlines() + process.stderr.readlines()]
        result = [s.strip() for s in result]
        return result

    def do(self, cmd):
        self.log(self.tab + cmd)
        result = Utils.run(cmd)
        result = [self.tab * 2 + s for s in result]
        self.log(result)
        return result

    @staticmethod
    def contain(key, line):
        lines = [line] if type(line) == str else line
        for line in lines:
            if line.find(key) > 0:
                return True
        return False

    @staticmethod
    def ok(result):
        # key pattern in error message
        err_msg = [
            "did not match any file(s) known to git",
            "you need to resolve your current index first",
            "error: remote did not send all necessary objects",
            "local changes to the following files would be overwritten by merge",
            "Automatic merge failed",
            "not something we can merge",
            "failed to push some refs"
        ]
        return len([err for err in err_msg if Utils.contain(err, result)]) == 0


class Project:
    def __init__(self, name, rev, up, path, remote):
        self.name = name
        self.rev = rev
        self.up = up
        self.path = path
        self.remote = remote


class Manifest:
    def read_settings(self):
        settings = {"xml": None, "merge": list(), "code": list()}
        if os.path.isfile(__git_auto_merge_last_settings__):
            with open(__git_auto_merge_last_settings__, "r") as f:
                settings = json.load(f) if f else None
        self.xml = settings["xml"]
        self.merge = settings["merge"]
        self.code = settings["code"]

    def __init__(self):
        self.read_settings()
        self.working = os.getcwd()
        candidates = [d for d in os.listdir(".") if os.path.isfile(os.path.join(".", d)) and d.endswith("Daily.xml")]
        if not candidates:
            return
        self.xml = self.xml if self.xml else Utils.choice("manifest file", candidates)
        print(self.xml)
        # ex: 20211112_OG6_S_202000231_Daily.xml -> OG6
        self.prj = self.xml[9:12] if self.xml.endswith("Daily.xml") else None
        self.work = "rel/ORI/" + self.xml[:-4]

        # try to find merge branch from daily build xml
        root = ElementTree.parse(self.xml).getroot()

        not_set = len(self.merge) <= 0
        while not_set:
            ups = [child.attrib.get('upstream') for child in root.findall('project') + root.findall('reset-project')]
            ups = [i for i in list(set(ups)) if i.endswith("PFAS") or i.endswith("PFAR") or i.endswith("BSP")]
            ups = [i for i in ups if i not in self.merge]
            self.merge += [Utils.choice("merge branch", list(set(ups)))]
            # get information from .repo
            self.code += [self.get_new_branch()]
            if "Y" != input(f"have another branch need to merge? (y/N)").upper():
                not_set = False

        # which project need merge ?
        self.remote, self.default_remote, self.server = self.get_remote(root)
        self.proj_lst = self.get_proj(root)

        # find source file location, /media/Workspace/tony/zon846 -> file://10.57.61.113/Workspace/tony/zon846
        if "Linux" == platform.system():
            p = Popen('hostname -I', shell=True, stdout=PIPE, stderr=STDOUT)
            ip = p.stdout.readline().strip().decode('utf-8')
            self.file = 'file://' + ip + '/' + "/".join(os.getcwd().split("/")[3:])

        self.check_info()

    def check_info(self):
        msg = "xml,prj,work,remote,default_remote,server,proj list"
        lost = [i for i, o in enumerate([self.xml, self.prj, self.work, self.remote,
                                         self.default_remote, self.server, self.proj_lst]) if not o]
        lost += [i for i, o in enumerate([self.merge, self.code], len(msg)) if len(o) <= 0]
        msg += ",merge, code"
        if lost:
            info = ','.join([msg.split(",")[i] for i in lost])
            raise BaseException(info)
        else:
            with open(__git_auto_merge_last_settings__, "w") as f:
                json.dump({"xml": self.xml, "merge": self.merge, "code": self.code}, f)

    @staticmethod
    def get_remote(root):
        remote = dict()
        default = root.find('default').attrib.get('remote')
        for name, fetch, review in [[child.attrib.get('name'), child.attrib.get('fetch'),  child.attrib.get('review')]
                                    for child in root.findall('remote')]:
            # "." -> "QC", remove "../"
            fetch = "QC" if fetch == '.' else fetch[3:] if fetch.startswith('../') else fetch
            remote[name] = fetch
            # http://gerrit3.fihtdc.com/ --> gerrit3.fihtdc.com
            if name == default:
                server = review[7:-1]
        return remote, default, server

    def get_proj(self, root):
        proj = []
        for child in root.findall('project') + root.findall('reset-project'):
            rev = child.attrib.get('revision')
            up = child.attrib.get('upstream') if child.attrib.get('upstream') else rev
            if up in self.merge:
                name = child.attrib.get('name')
                path = child.attrib.get('path') if child.attrib.get('path') else name
                remote = child.attrib.get('remote') if child.attrib.get('remote') else self.default_remote
                proj.append(Project(name, rev, up, path, remote))
        return proj

    def get_new_branch(self):
        # find the new branch from .repo
        root = ElementTree.parse('.repo/manifest.xml').getroot()
        opts = [child.attrib.get('name') for child in root.findall('include')]
        opts = [i for i in opts if i.endswith("PFAR.xml") or i.endswith("PFAS.xml")]
        xml = Utils.choice("merge xml", opts)
        root = ElementTree.parse('.repo/manifests/' + xml).getroot()
        opts = list(set([child.attrib.get('revision') for child in root.findall('project') + root.findall('reset-project')]))
        opts = [i for i in opts if i and i not in self.code]
        return Utils.choice("revision", opts)

    def get_info(self):
        localtime = time.asctime(time.localtime(time.time()) )
        result = f"******************integration info****************** ver. {__tool_version__} {localtime}\n"
        for i, merge in enumerate(self.merge):
            result += f"Merge#{i} from       :  {merge} at {self.xml}\n"
            result += f"Merge#{i} into       :  {self.code[i]}\n"
        result += f"Working branch     :  {self.work}\n"
        result += f"Account            :  {__account__}\n"
        result += f"Gerrit Server      :  {self.server}\n"
        result += f"********************************************************\n"
        result += f"remember commit each git project after conflict fixed"
        return result


class Operation:
    def __init__(self, mani, fun, utils):
        self.mani = mani
        self.fun = fun
        self.tag = None
        self.utils = utils
        pass

    def set_tag(self, tag):
        self.tag = tag

    def gen_conflict(self, proj, result):
        # CONFLICT(content): Merge conflict in src/com/android/bluetooth/btservice/AdapterService.java
        #    ===>
        # CONFLICT(content): AdapterService.java
        #   file://10.57.61.113/Workspace/tony/og6/.../AdapterService.java
        #   http://10.56.56.7:7474/gitweb/?p=QC_19_21/platform/fra...hb=refs/heads/SHARP/dev/QSSI/12004300/AQUOS/PFAS;a=blame
        file_regex = re.compile(r".*Merge conflict in (.*)")
        files = [(line.split(":")[0].strip(), file_regex.search(line).group(1)) for line in result if file_regex.search(line)]
        self.utils.log(f"---> {self.tag}", False)
        for head, file in files:
            msg = f"  {head}: {os.path.basename(file)}\n"
            msg += Utils.tab + os.path.join(self.mani.file, proj.path, file)
            self.utils.log(msg, False)
            msg = f"{Utils.tab}http://{self.mani.server}:7474/gitweb/?p={self.mani.remote[proj.remote]}/{proj.name}.git;"
            msg += f"f={file};hb=refs/heads/{proj.up};a=blame"
            self.utils.log(msg, False)
        self.utils.log(f"<--- {self.tag}", False)

    def exec(self, proj):
        if self.fun == "merge":
            return self.merge(proj)
        if self.fun == "push":
            return self.push(proj)
        if self.fun == "verify":
            return self.verify(proj)

    def merge(self, proj):
        good = self.utils.ok(self.utils.do(f"git checkout {self.mani.code}"))
        if good:
            result = self.utils.do(f"git branch --contains {proj.rev}")
            no_merge = Utils.contain(self.mani.code, result)
            if no_merge:
                self.utils.log(Utils.tab + '# no need to merge #')
            else:
                self.utils.do(f"git config user.name {__account__} && git config user.email {__email__}")
                # try again when git fetch failure
                if not self.utils.ok(self.utils.do(f"git fetch {proj.remote} --unshallow")):
                    self.utils.do(f"git fetch {proj.remote} --unshallow")
                self.utils.do(f"git branch {self.mani.work} {proj.rev}")
                self.utils.do('git branch -v')
                result = self.utils.do(f'git merge --no-ff {self.mani.work}')
                good = self.utils.ok(result)
                if not good:
                    self.gen_conflict(proj, result)
        status = "<ERROR>" if not good else ("<NO MERGE>" if no_merge else "")
        return good, status

    def push(self, proj):
        result = self.utils.do("git status")
        good = Utils.contain("nothing to commit, working tree clean", result)
        no_push = Utils.contain("Your branch is up to date", result)
        no_change = False
        if good and not no_push:
            cmd = f"git push ssh://{__account__}@{self.mani.server}:29418/{self.mani.remote[proj.remote]}/"
            cmd += f"{proj.name} HEAD:refs/for/{self.mani.code}"
            result = self.utils.do(cmd)
            no_change = Utils.contain("no new changes", result)
            good = Utils.ok(result)
            
        status = "<ERROR>" if not good else ("<NO CHANGE>" if no_change or no_push else "")        
        return good, status

    def verify(self, proj):
        print(f"{self.mani.merge}, {proj.up}")
        code = self.mani.code[self.mani.merge.index(proj.up)]
        good = self.utils.ok(self.utils.do(f"git checkout {code}"))
        good = self.utils.ok(self.utils.do(f"git fetch")) if good else good
        good = self.utils.ok(self.utils.do(f"git pull")) if good else good
        if good:
            result = self.utils.do(f"git branch --contains {proj.rev}")
            good = Utils.contain(code, result)
        if good:
            result = self.utils.do("git status")
            good = Utils.contain("up to date", result)
            good = Utils.contain("working tree clean", result) if good else good
        status = "<ERROR>" if not good else ""
        return good, status


class Gerrit:
    def __init__(self, server):
        self.server = server

    def query(self, ask):
        cmd = f"ssh -p 29418 {self.server} -l tonycylin gerrit query --format=JSON --current-patch-set {ask}"
        cmd += " limit:1"
        result = Utils.run(cmd)
        return result


def setup(args):
    mani = Manifest()
    print(mani.get_info())
    utils = Utils(mani.working)

    op = Operation(mani, "merge", utils) if args.merge else None
    op = Operation(mani, "push", utils) if not op and args.push else op
    op = Operation(mani, "verify", utils) if not op and args.verify else op
    if not op:
        raise BaseException("No operation")
    return input(f"ready to {op.fun}? (y)es, (N)o, (r)e-set: ").upper(), op, utils, mani


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--merge", help="merge project base on daily build", action="store_true")
    parser.add_argument("-p", "--push", help="push project base on daily build", action="store_true")
    parser.add_argument("-v", "--verify", help="verify that the daily build is merged into the new branch",
                        action="store_true")
    args = parser.parse_args()

    while True:
        ans, op, utils, mani = setup(args)
        if "R" != ans:
            break
        elif os.path.isfile(__git_auto_merge_last_settings__):
            os.remove(__git_auto_merge_last_settings__)

    if "Y" != ans:
        return

    if False:  # debug only
        mani.proj_lst = [i for i in mani.proj_lst if i.path == "LA.QSSI.12/LINUX/android/device/qcom/qssi"]

    good = True
    for i, proj in enumerate(mani.proj_lst):
        tag = f"[{i}/{len(mani.proj_lst)}] {proj.name}, {proj.path}, {proj.rev}"
        op.set_tag(tag)
        path = os.path.join(mani.working, proj.path)
        utils.log(f"\n---> {op.fun}: {tag}")
        status = "<ERROR>"
        if os.path.isdir(path):
            os.chdir(path)
            g, status = op.exec(proj)
            good = good & g
        else:
            good = False
            utils.log(f"<--- {op.fun}: {status} folder not exist ({proj.path}) {tag}")
        utils.log(f"<--- {op.fun}: {status}{tag}")
    msg = "everything is good" if good else "something is wrong"
    utils.log(f"\n[{msg}]", color=True)


if __name__ == '__main__':
    main()
