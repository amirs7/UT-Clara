#!/usr/bin/env python
import glob
import json
import os
import shutil

from clara.clustering import Clustering
from clara.feedback import FeedGen, Feedback
from clara.feedback_repair import RepairFeedback
from clara.interpreter import getlanginter
from clara.matching import Matching
from clara.model import expr_to_dict
from clara.parser import getlangparser
from clara.repair import Repair

VERBOSE = 1


class Clara(object):

    def __init__(self, inputs, lang='cpp'):
        self.lang = lang
        self.parser = getlangparser(self.lang)
        self.interpreter = getlanginter(self.lang)
        self.entry_function = 'main'
        self.inputs = inputs
        self.clusters_dir = './clusters'
        self.models = []
        self.max_cost = 100
        global VERBOSE

    def eval(self):
        inter = self.interpreter(entryfnc=self.entry_function)
        # print(self.models[0])
        trace = inter.run(self.models[0], args=None, ins=self.inputs)
        return trace

    def process_source(self, src):
        with open(src, 'r', encoding="utf-8") as f:
            print("processing", src)
            code = f.read()
            print("processed", src)
        model = self.parser.parse_code(code)
        model.name = src
        return model

    def process_sources(self, sources):
        self.models = []
        for src in sources:
            model = self.process_source(src)
            self.models.append(model)

    def match(self):
        matching = Matching(verbose=True)
        m = matching.match_programs(self.models[0], self.models[1],
                                    self.interpreter, ins=[self.inputs], entryfnc=self.entry_function)
        if m:
            return True
        else:
            return False

    def cluster(self):
        M = Matching()
        C = Clustering(M)
        existing = []
        shutil.rmtree(self.clusters_dir, ignore_errors=True)
        os.mkdir(self.clusters_dir)
        for f in glob.glob(os.path.join(self.clusters_dir, "*." + self.lang)):
            model = self.process_source(f)
            existing.append(model)
        print("Found %d existing clusters" % (len(existing)))

        new, mod = C.cluster(self.models, self.interpreter, ins=[self.inputs], entryfnc=self.entry_function,
                             existing=existing)

        print("Done, %d new clusters, %d modified clusters" % (len(new), len(mod)))

        cluster_files = []
        # Add new clusters
        for f in new:
            f.new_name = os.path.join(self.clusters_dir, f.new_name)
            print("NEW:", f.name, "->", f.new_name)
            cluster_files.append(f.new_name)

            # Copy the source file
            if os.path.exists(f.new_name):
                print("Filename '%s' already exists!")
            shutil.copyfile(f.name, f.new_name)

            # Dump expressions
            f.name = f.new_name
            self.dump_expressions(f)

        # Write modifications for the modified clusters
        for f in mod:
            print("MOD:", f.name)
            self.dump_expressions(f)
        return cluster_files

    def dump_expressions(self, model):

        exprs = []
        for fnc in model.getfncs():
            if not hasattr(fnc, 'repair_exprs'):
                continue
            rex = fnc.repair_exprs

            for loc in rex:
                for var in rex[loc]:
                    exprs.append({
                        "fnc": fnc.name,
                        "loc": loc,
                        "var": var,
                        "expr": expr_to_dict(fnc.getexpr(loc, var)),
                        "src": None,
                    })
                    for expr in set(rex[loc][var]):
                        exprs.append({
                            "fnc": fnc.name,
                            "loc": loc,
                            "var": var,
                            "expr": expr_to_dict(expr),
                            "src": expr.src,
                        })

        ext = '.' + self.lang
        exprs_filename = model.name.replace(ext, '-exprs.json')
        with open(exprs_filename, 'w') as f:
            json.dump(exprs, f, indent=2)

    def repair(self):
        R = Repair(verbose=False)
        r = R.repair(self.models[0], self.models[1], self.interpreter, ins=[self.inputs], entryfnc=self.entry_function)

        if r:
            txt = RepairFeedback(self.models[1], self.models[0], r)
            txt.genfeedback()
            print('Repairs:')
            print('\n'.join(['  * %s' % (x,) for x in txt.feedback]))
        else:
            print('No repair!')

    def feedback(self):
        F = FeedGen(feedmod=RepairFeedback)
        impl = self.models[-1]
        specs = self.models[:-1]

        feed = F.generate(
            impl, specs, self.interpreter, ins=[self.inputs], ignoreret=True,
            entryfnc=self.entry_function)

        if feed.status == Feedback.STATUS_REPAIRED:
            if self.max_cost > 0 and feed.cost > self.max_cost:
                print('max cost exceeded (%d > %d)', feed.cost, self.max_cost)
                return
            for f in feed.feedback:
                print('*', f)
        elif feed.status == Feedback.STATUS_ERROR:
            print(feed.error)
        else:
            print(feed.statusstr())
