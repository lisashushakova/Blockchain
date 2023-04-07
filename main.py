import asyncio
import concurrent.futures
import json
import os
import sys
import time
from socket import socket, AF_INET, SOCK_DGRAM

from blockchain import Blockchain

NODE_SOCKETS = (
    ('127.0.0.1', 60000), # SOCKET FOR TESTING
    ('127.0.0.1', 60001),
    ('127.0.0.1', 60002),
    ('127.0.0.1', 60003),
)

class Node:

    def __init__(self, addr):
        if addr not in NODE_SOCKETS:
            raise ValueError('Invalid node socket')
        elif addr == ('127.0.0.1', 60000):
            raise ValueError('This socket is for testing only')

        self.addr = addr
        self.blockchain = Blockchain()
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.bind(addr)
        self.socket.setblocking(False)
        self.stop = False

    def receive_block(self):
        try:
            block = json.loads(self.socket.recv(1024).decode())
            return block

        except BlockingIOError:
            # No block received
            return None
        except ConnectionResetError:
            # Disconnection occurred
            return None

    def send_block(self, block):
        for node_addr in NODE_SOCKETS:
            if node_addr != self.addr:
                self.socket.sendto(json.dumps(block).encode(), node_addr)

    def listen_nodes(self):
        while True:
            block = self.receive_block()
            if block is not None:
                index = block.get('index')
                # Received new block
                print(f'Received block {block.get("hash")[:4]}')
                if index == len(self.blockchain.chain):
                    # Check for valid hash chaining
                    if len(self.blockchain.chain) == 0 or block.get('prev_hash') == self.blockchain.chain[-1].get('hash'):
                        self.blockchain.chain.append(block)
                        self.blockchain.interrupt()
                        print(f'Inserted block {block.get("hash")[:4]}')
                    else:
                        print(f'Block {block.get("hash")[:4]} rejected: Invalid hash')

                # Received outdated block with lesser index
                elif index < len(self.blockchain.chain):
                    print(f'Received block with lesser index {block.get("hash")[:4]}')
                    my_block = self.blockchain.chain[index]
                    if my_block.get('timestamp') > block.get('timestamp'):
                        if block.get('prev_hash') == self.blockchain.chain[index-1].get('hash'):
                            self.blockchain.interrupt()
                            self.blockchain.drop_tail(index)
                            self.blockchain.chain.append(block)
                            self.blockchain.interrupt()
                            print(f'Inserted block {block.get("hash")[:4]}')
                    elif my_block.get('timestamp') < block.get('timestamp'):
                        for my_block in self.blockchain.chain[index:]:
                            self.send_block(my_block)
                        print(f'Rejected block {block.get("hash")[:4]}, send better one {my_block.get("hash")[:4]}')

            if self.stop:
                break

    def generate_chain(self, generation_delay):
        if generation_delay is not None:
            time.sleep(generation_delay)
        while True:
            new_block = self.blockchain.generate_block()
            if new_block:
                self.send_block(new_block)
                print(f'Sent block {new_block.get("hash")[:4]}')

    def block_count_watcher(self, block_count):
        print(f'Started with target block count {block_count}')
        while True:
            time.sleep(1)
            if len(self.blockchain.chain) >= block_count or self.stop:
                self.stop = True
                break

    def timeout_watcher(self, timeout):
        print(f'Started with timeout {timeout}')
        start = time.perf_counter()
        while True:
            time.sleep(1)
            if time.perf_counter() - start >= timeout or self.stop:
                self.stop = True
                break

    async def async_run(self, timeout, block_count, generation_delay):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        loop = asyncio.get_event_loop()
        done, pending = await asyncio.wait(
            fs={
                loop.run_in_executor(executor, Node.listen_nodes, self),
                loop.run_in_executor(executor, Node.generate_chain, self, generation_delay),
                loop.run_in_executor(executor, Node.timeout_watcher, self, timeout),
                loop.run_in_executor(executor, Node.block_count_watcher, self, block_count),
            }, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.wait(pending)

    def run(self, timeout=3600, block_count=1000, generation_delay=None, start_delay=None):
        if start_delay is not None:
            time.sleep(start_delay)
        asyncio.run(self.async_run(timeout, block_count, generation_delay))
        self.socket.close()
        return self.blockchain.chain[:block_count]


if __name__ == '__main__':
    _, host, port, logging = sys.argv

    if logging == "True":
        pass
    elif logging == "False":
        sys.stdout = open(os.devnull, 'w')
    else:
        raise ValueError('Invalid logging argument value')

    node = Node(addr=(host, int(port)))

    blockchain = node.run(block_count=50)
    print(json.dumps(blockchain, indent=4))

    time.sleep(2)
    sys.stdout = sys.__stdout__
    print(json.dumps(blockchain[-1], indent=4))