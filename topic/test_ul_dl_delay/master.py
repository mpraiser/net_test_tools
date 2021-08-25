import time
import random
import asyncio

import topic.test_ul_dl_delay.frame as frame
from topic.test_loss import generate
from utils import hex_str


class Protocol(asyncio.DatagramProtocol):
    def __init__(self, buffer: asyncio.Queue):
        self.transport = None
        self.buffer = buffer

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data, addr):
        # ignore addr
        t_recv = time.time()
        asyncio.ensure_future(self.buffer.put(
            (t_recv, data)
        ))


async def master_tx(
        eof_received: asyncio.Future,
        buffer: asyncio.Queue,
        dataset: list,
        local: tuple[str, int],
        remote: tuple[str, int],
        *,
        interval: float = 0,
        simulate_loss: bool
):
    loop = asyncio.get_running_loop()
    transport: asyncio.DatagramTransport
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: Protocol(buffer),
        local_addr=local,
        remote_addr=remote
    )
    for seq, packet in enumerate(dataset):
        eof = (seq >= len(dataset) - 1)
        data = frame.serialize(seq, eof, time.time(), 0, packet)
        if (not simulate_loss) or eof or random.random() > 0.5:
            transport.sendto(data)
        await asyncio.sleep(interval)

    await eof_received
    transport.close()


async def master_rx(eof_received: asyncio.Future, buffer: asyncio.Queue):
    # TODO: 添加包正确性校验
    # TODO: 添加丢包率
    while True:
        t_recv, data = await buffer.get()
        seq, eof, t_master, t_slave, payload = frame.deserialize(data)
        t_ul = (t_slave - t_master) * 1000
        t_dl = (t_recv - t_slave) * 1000
        print(f"seq = {seq}, ul = {t_ul:.2f} ms, dl = {t_dl:.2f} ms: {hex_str(payload)}")
        if eof:
            print(f"receive EOF!")
            eof_received.set_result(True)
            break


async def main(
        local: tuple[str, int],
        remote: tuple[str, int],
        max_packet_size: int,
        n_packet: int,
        *,
        random_size: bool = True,
        interval: float = 0,
        simulate_loss: bool
):
    max_payload_size = max_packet_size - frame.prefix_size
    dataset = list(generate(
        max_payload_size, n_packet, random_size=random_size
    ))
    eof_received = asyncio.Future()
    buffer = asyncio.Queue()
    await asyncio.gather(
        asyncio.create_task(master_tx(
            eof_received, buffer, dataset, local, remote,
            interval=interval, simulate_loss=simulate_loss
        )),
        asyncio.create_task(master_rx(eof_received, buffer))
    )


def run_master(
        local: tuple[str, int],
        remote: tuple[str, int],
        max_packet_size: int,
        n_packet: int,
        *,
        random_size: bool = True,
        interval: float = 0,
        simulate_loss: bool = False
):
    asyncio.run(main(
        local, remote, max_packet_size, n_packet,
        random_size=random_size, interval=interval, simulate_loss=simulate_loss
    ))