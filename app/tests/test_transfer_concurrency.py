import threading


RESULTS = []


def worker():

    RESULTS.append(True)


def test_concurrency_harness():

    threads = []

    for _ in range(10):

        thread = threading.Thread(
            target=worker
        )

        thread.start()

        threads.append(thread)

    for thread in threads:
        thread.join()

    assert len(RESULTS) == 10