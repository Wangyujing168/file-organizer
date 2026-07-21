"""测试哈希器模块"""

from file_organizer.hasher import FileHasher, compute_file_md5


class TestFileHasher:
    """测试 FileHasher 类"""

    def test_hash_file_xxh3(self, sample_files):
        temp_dir, files = sample_files
        hasher = FileHasher(algorithm="xxh3_128")

        h1 = hasher.hash_file(files["hello1"])
        h2 = hasher.hash_file(files["hello2"])
        h3 = hasher.hash_file(files["unique"])

        # 相同内容应该有相同哈希
        assert h1 == h2
        # 不同内容应该有不同哈希
        assert h1 != h3
        # 哈希值不为空
        assert len(h1) > 0

    def test_hash_file_xxh64(self, sample_files):
        temp_dir, files = sample_files
        hasher = FileHasher(algorithm="xxh64")

        h = hasher.hash_file(files["hello1"])
        assert len(h) > 0

    def test_hash_empty_file(self, sample_files):
        temp_dir, files = sample_files
        hasher = FileHasher()
        h = hasher.hash_file(files["empty"])
        assert len(h) > 0

    def test_hash_partial_large_file(self, sample_files):
        temp_dir, files = sample_files
        hasher = FileHasher()
        # big.txt is 10000 bytes, under threshold - will use full hash
        h_full = hasher.hash_file(files["big"])
        assert len(h_full) > 0

    def test_compute_md5(self, sample_files):
        temp_dir, files = sample_files
        h1 = compute_file_md5(files["hello1"])
        h2 = compute_file_md5(files["hello2"])

        assert h1 == h2
        assert len(h1) == 32  # MD5 is 32 hex chars

    def test_hash_nonexistent_file(self, temp_dir):
        hasher = FileHasher()
        h = hasher.hash_file(temp_dir / "does_not_exist.txt")
        assert h == ""
