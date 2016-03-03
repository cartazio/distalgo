
import da
PatternExpr_170 = da.pat.TuplePattern([da.pat.ConstantPattern('Y')])
PatternExpr_180 = da.pat.TuplePattern([da.pat.ConstantPattern('Z')])

class P(da.DistProcess):

    def __init__(self, parent, initq, channel, props):
        super().__init__(parent, initq, channel, props)
        self._events.extend([da.pat.EventPattern(da.pat.ReceivedEvent, '_PReceivedEvent_0', PatternExpr_170, sources=None, destinations=None, timestamps=None, record_history=None, handlers=[self._P_handler_169]), da.pat.EventPattern(da.pat.ReceivedEvent, '_PReceivedEvent_1', PatternExpr_180, sources=None, destinations=None, timestamps=None, record_history=None, handlers=[self._P_handler_179])])

    def setup(self):
        self.d = 1
        self.x = 1

    def _da_run_internal(self):
        super()._label('l', block=False)
        _st_label_190 = 0
        while True:
            if (_st_label_190 == 2):
                break
            elif (_st_label_190 == 1):
                super()._label('l', block=True)
            _st_label_190 = 1
            if (self.d == 1):
                self.output('d is 1.')
            elif (self.x == 1):
                self.output('x is 1.')
            else:
                self.output('neither d nor x is 1.')
                _st_label_190 += 1

    def _P_handler_169(self):
        self.d = 0
    _P_handler_169._labels = None
    _P_handler_169._notlabels = None

    def _P_handler_179(self):
        self.x = 0
    _P_handler_179._labels = None
    _P_handler_179._notlabels = None

class Q(da.DistProcess):

    def __init__(self, parent, initq, channel, props):
        super().__init__(parent, initq, channel, props)
        self._events.extend([])

    def setup(self, ps):
        self.ps = ps
        pass

    def _da_run_internal(self):
        self.output("Sending 'X'.")
        self._send(('X',), self.ps)
        super()._label('_st_label_222', block=False)
        _st_label_222 = 0
        self._timer_start()
        while (_st_label_222 == 0):
            _st_label_222 += 1
            if False:
                _st_label_222 += 1
            elif self._timer_expired:
                _st_label_222 += 1
            else:
                super()._label('_st_label_222', block=True, timeout=2)
                _st_label_222 -= 1
        self.output("Sending 'X'.")
        self._send(('X',), self.ps)
        super()._label('_st_label_232', block=False)
        _st_label_232 = 0
        self._timer_start()
        while (_st_label_232 == 0):
            _st_label_232 += 1
            if False:
                _st_label_232 += 1
            elif self._timer_expired:
                _st_label_232 += 1
            else:
                super()._label('_st_label_232', block=True, timeout=2)
                _st_label_232 -= 1
        self.output("Sending 'Y'.")
        self._send(('Y',), self.ps)
        super()._label('_st_label_242', block=False)
        _st_label_242 = 0
        self._timer_start()
        while (_st_label_242 == 0):
            _st_label_242 += 1
            if False:
                _st_label_242 += 1
            elif self._timer_expired:
                _st_label_242 += 1
            else:
                super()._label('_st_label_242', block=True, timeout=2)
                _st_label_242 -= 1
        self.output("Sending 'Z'.")
        self._send(('Z',), self.ps)
        while False:
            self.output('Fail!')

def main():
    ps = da.new(P, [], 1)
    qs = da.new(Q, [ps], 1)
    da.start(ps)
    da.start(qs)
