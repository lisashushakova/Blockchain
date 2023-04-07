import json
import random
import string
import time
from hashlib import sha256


class Blockchain:

    def __init__(self):
        self.chain = []
        self.interrupt_flag = False

    def generate_block(self, proof_of_work=4):
        if len(self.chain) == 0:
            prev_hash = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(64))
        elif len(self.chain) > 0:
            prev_hash = self.chain[-1].get('hash')
        else:
            return None
        index = len(self.chain)
        data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(256))
        nonce = 0
        step = random.randint(1, 20)
        while True:
            if self.interrupt_flag:
                self.interrupt_flag = False
                return None
            hash = sha256((''.join(list(map(str, [index, prev_hash, data, nonce])))).encode()).hexdigest()
            if hash.endswith('0' * proof_of_work):
                new_block = {
                    'index': index,
                    'prev_hash': prev_hash,
                    'data': data,
                    'nonce': nonce,
                    'hash': hash,
                    'timestamp': time.time()
                }
                self.chain.append(new_block)
                return new_block

            nonce += step

    def interrupt(self):
        self.interrupt_flag = True

    def drop_tail(self, from_index):
        self.chain = self.chain[:from_index]

