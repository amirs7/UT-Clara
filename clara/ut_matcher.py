from clara.common import print_trace
from clara.model import isprimed, prime, Const, VAR_COND


class WhileModel:
    def __init__(self, pre, condition, body, after):
        self.pre = pre
        self.condition = condition
        self.body = body
        self.after = after

    def check_transition(self, prev, cur):
        return (prev == self.condition and cur == self.body) \
               or (prev == self.condition and cur == self.after) \
               or (prev == self.body and cur == self.condition)

    def all_locations(self):
        return {self.condition, self.body, self.after}


def find_simple_while(model):
    main_function = model.fncs['main']
    pre = None
    for condition in main_function.loctrans:
        if main_function.numtrans(condition) < 2:
            pre = condition
            continue
        body = main_function.trans(condition, True)
        after = main_function.trans(condition, False)
        if main_function.trans(body, True) == condition and main_function.numtrans(after) == 0:
            return WhileModel(pre, condition, body, after)
    return None


def fold_trace(trace, while_model):
    mem = None
    prev = None
    start = None
    end = None
    for i in range(len(trace)):
        cur = trace[i]
        if cur[1] == while_model.condition and start is None:
            start = i
        if prev is not None and while_model.check_transition(prev[1], cur[1]):
            mem = cur[2]
        prev = cur
        if cur[1] == while_model.after:
            end = i
            break
    print(start, end)
    assert start >= 1
    pre_start_mem = trace[start - 1][2]
    for v in mem:
        if isprimed(v):
            pre_start_mem[v] = mem[v]
    new_trace = [*trace[:start - 1], (trace[start - 1][0], trace[start - 1][1], pre_start_mem), *trace[end + 1:]]
    return new_trace


def remove_while(model, new_trace):
    main_function = model.fncs['main']
    while_model = find_simple_while(model)
    expressions = {}
    for loc in main_function.locexprs:
        if loc in while_model.all_locations():
            expressions.update(main_function.locexprs[loc])
    pre_while_loc = 1
    for t in new_trace:
        if t[1] == while_model.pre:
            break
    for var in expressions:
        if var == VAR_COND:
            continue
        main_function.replace_expr(pre_while_loc, var, Const(str(t[2][prime(var)])))

    main_function.loctrans[pre_while_loc][True] = main_function.trans(while_model.after, True)
    main_function.loctrans[pre_while_loc][False] = main_function.trans(while_model.after, False)
    main_function.rmloc(while_model.condition)
    main_function.rmloc(while_model.body)
    main_function.rmloc(while_model.after)
    return model


def process_model(model, trace):
    while_model = find_simple_while(model)
    new_trace = fold_trace(trace, while_model)
    new_model = remove_while(model, new_trace)
    return new_model
