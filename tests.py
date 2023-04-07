import hashlib
import asyncio
import concurrent
import json
import time
import unittest
from socket import socket, AF_INET, SOCK_DGRAM

from main import Node, NODE_SOCKETS
from blockchain import Blockchain


class BlockchainUnitTests(unittest.TestCase):

    def test_block_generation(self):
        blockchain = Blockchain()
        block = blockchain.generate_block()

        binary = ''.join(list(map(str, (
            block.get('index'),
            block.get('prev_hash'),
            block.get('data'),
            block.get('nonce')
        )))).encode()

        calculated_hash = hashlib.sha256(binary).hexdigest()

        assert block.get('index') == 0
        assert calculated_hash == block.get('hash')

    def test_block_generation_interrupt(self):
        blockchain = Blockchain()
        blockchain.interrupt()
        block = blockchain.generate_block()

        assert block is None

    def test_blockchain_generation(self):
        blockchain = Blockchain()
        for _ in range(20):
            blockchain.generate_block()

        for i, _ in enumerate(blockchain.chain):
            assert blockchain.chain[i].get('index') == i
            if i > 1:
                assert (blockchain.chain[i - 1].get('hash') == blockchain.chain[i].get('prev_hash'))

    def test_chain_drop_tail(self):
        blockchain = Blockchain()
        for _ in range(10):
            blockchain.generate_block()
        blockchain.drop_tail(5)
        assert len(blockchain.chain) == 5


class BlockchainIntegrationTests(unittest.TestCase):

    def setUp(self):
        addr = ('127.0.0.1', 60000)
        self.test_socket = socket(AF_INET, SOCK_DGRAM)
        self.test_socket.bind(addr)
        self.test_socket.setblocking(False)
        self.received_blocks = []

    def tearDown(self):
        self.test_socket.close()

    def send_block(self, block, addr, delay=None):
        if delay is not None:
            time.sleep(delay)
        self.test_socket.sendto(json.dumps(block).encode(), addr)

    def receive_block(self):
        while True:
            try:
                block = json.loads(self.test_socket.recv(1024).decode())
                self.received_blocks.append(block)
                if len(self.received_blocks) >= 10:
                    break

            except BlockingIOError:
                # No block received
                pass

            except ConnectionResetError:
                # Disconnection occurred
                pass

    def test_valid_block_receive(self):
        addr = ('127.0.0.1', 60001)
        node = Node(addr)

        block = {
            "index": 0,
            "prev_hash": "cvza9b3ew6sv82s7kp1saqvb9gjmyvvslejn0uf853a22mzc5tgc6zapd1dhqeuh",
            "data": "sySMO8SOgHGzbuDTnAo7rDqLbtEP3YkwDBs9x4wgOTzi0Xh3C64N2T4Nhht3NnEz"
                    "yia9mIe9F7LjdAj8KWQqtK4WgHiSgGn17MedPUHm22JlFYtRmZDhWq3ODd37MPfV"
                    "mav1zpipKg022553imTQODkPfAoiVkJ3sv3EVrRbbBe2iYOvgQVvcKfNH3Ci7FfY"
                    "WQUf8DrK1ahb8fWbA6OSSBTeb5W7wWR7O6eLcP6mvnoSEdAoRtUDWPZ1avlV5QM2",
            "nonce": 34173,
            "hash": "7cb8f748b7aed3b97cc1a34ff2afb3c8dc8ced4ca8e12ef8cd73c4ebf22d0000",
            "timestamp": 1680859052.3816102
        }

        async def run():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            loop = asyncio.get_event_loop()
            await asyncio.wait(
                fs={
                    loop.run_in_executor(executor, Node.run, node, 10, 50, 2),
                    loop.run_in_executor(executor, BlockchainIntegrationTests.send_block, self, block, addr, 1),
                }, return_when=asyncio.ALL_COMPLETED
            )

        asyncio.run(run())

        assert node.blockchain.chain[0] == block

    def test_invalid_block_receive(self):
        addr = ('127.0.0.1', 60001)
        node = Node(addr)

        block = {
            "index": 0,
            "prev_hash": "cvza9b3ew6sv82s7kp1saqvb9gjmyvvslejn0uf853a22mzc5tgc6zapd1dhqeuh",
            "data": "sySMO8SOgHGzbuDTnAo7rDqLbtEP3YkwDBs9x4wgOTzi0Xh3C64N2T4Nhht3NnEz"
                    "yia9mIe9F7LjdAj8KWQqtK4WgHiSgGn17MedPUHm22JlFYtRmZDhWq3ODd37MPfV"
                    "mav1zpipKg022553imTQODkPfAoiVkJ3sv3EVrRbbBe2iYOvgQVvcKfNH3Ci7FfY"
                    "WQUf8DrK1ahb8fWbA6OSSBTeb5W7wWR7O6eLcP6mvnoSEdAoRtUDWPZ1avlV5QM2",
            "nonce": 34173,
            "hash": "7cb8f748b7aed3b97cc1a34ff2afb3c8dc8ced4ca8e12ef8cd73c4ebf22d0000",
            "timestamp": 1680859052.3816102
        }

        async def run():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            loop = asyncio.get_event_loop()
            await asyncio.wait(
                fs={
                    loop.run_in_executor(executor, Node.run, node, 10, 50),
                    loop.run_in_executor(executor, BlockchainIntegrationTests.send_block, self, block, addr, 5),
                }, return_when=asyncio.ALL_COMPLETED
            )

        asyncio.run(run())

        for node_block in node.blockchain.chain:
            assert block != node_block

    def test_block_send(self):
        addr = ('127.0.0.1', 60001)
        node = Node(addr)

        async def run():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            loop = asyncio.get_event_loop()
            await asyncio.wait(
                fs={
                    loop.run_in_executor(executor, Node.run, node, 20, 10),
                    loop.run_in_executor(executor, BlockchainIntegrationTests.receive_block, self),
                }, return_when=asyncio.ALL_COMPLETED
            )

        asyncio.run(run())
        for block in self.received_blocks:
            assert block in node.blockchain.chain

    def test_chain_sync(self):
        node_1 = Node(addr=('127.0.0.1', 60001))
        node_2 = Node(addr=('127.0.0.1', 60002))

        async def run():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            loop = asyncio.get_event_loop()
            await asyncio.wait(
                fs={
                    loop.run_in_executor(executor, Node.run, node_1, 30, 20),
                    loop.run_in_executor(executor, Node.run, node_2, 30, 20, 0, 1),
                }, return_when=asyncio.ALL_COMPLETED
            )

        asyncio.run(run())
        assert node_1.blockchain.chain[:20] == node_2.blockchain.chain[:20]

    def test_triple_node(self):
        block_count = 20

        node_1 = Node(addr=('127.0.0.1', 60001))
        node_2 = Node(addr=('127.0.0.1', 60002))
        node_3 = Node(addr=('127.0.0.1', 60003))

        async def run():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=12)
            loop = asyncio.get_event_loop()
            await asyncio.wait(
                fs={
                    loop.run_in_executor(executor, Node.run, node_1, 60, 40),
                    loop.run_in_executor(executor, Node.run, node_2, 60, 40, 3),
                    loop.run_in_executor(executor, Node.run, node_3, 60, 40, 3),
                }, return_when=asyncio.ALL_COMPLETED
            )

        asyncio.run(run())

        assert node_1.blockchain.chain[:block_count] == node_2.blockchain.chain[:block_count] == node_3.blockchain.chain[:block_count]


class BlockchainSystemTests(unittest.TestCase):

    def test_socket_closure(self):

        node_1 = Node(addr=('127.0.0.1', 60001))
        node_2 = Node(addr=('127.0.0.1', 60002))
        node_3 = Node(addr=('127.0.0.1', 60003))

        async def run():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=12)
            loop = asyncio.get_event_loop()
            await asyncio.wait(
                fs={
                    loop.run_in_executor(executor, Node.run, node_1, 60, 20),
                    loop.run_in_executor(executor, Node.run, node_2, 60, 20, 1),
                    loop.run_in_executor(executor, Node.run, node_3, 60, 20, 1),
                }, return_when=asyncio.ALL_COMPLETED
            )

        asyncio.run(run())

        for addr in NODE_SOCKETS:
            with socket(AF_INET, SOCK_DGRAM) as sock:
                try:
                    sock.bind(addr)
                except OSError:
                    self.fail('Node socket was not closed')


if __name__ == '__main__':
    unittest.main()
