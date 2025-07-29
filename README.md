# COWList 🐄 -- An Immutable, Copy-on-Write List for Python

An efficient, immutable, type-safe copy-on-write (COW) list implementation for Python 2+.

COWList provides a persistent, immutable list-like data structure where all mutating operations return a new instance, allowing shared storage between list versions until modifications are made. This results in efficient memory use, O(1) indexing, and safe concurrency patterns.

## Features

- ✅ **Immutable**: All operations return a new instance.
- 🧠 **Copy-on-Write**: Physical storage is shared until a mutation is required.
- ⚡ **Efficient**:
    - O(1) indexing and slicing
    - O(1) appending (if the current instance is contiguous and not a sliced view)
    - O(k) extending (if the current instance is contiguous and not a sliced view)
- 🧩 **Pythonic**: Implements the full `collections.abc.Sequence` protocol. Fully typed.
- 🔐 **Hashable**: Suitable for use as dict keys or set elements (when elements are hashable).
- 🧪 **Testable & Extendable**: Clean architecture for experimentation or educational purposes.

## Installation

```bash
pip install cowlist
```

## Usage

```python
from cowlist import COWList

# --- Construction ---
lst = COWList([1, 2, 3])
assert list(lst) == [1, 2, 3]

empty = COWList()
assert list(empty) == []
assert len(empty) == 0

# --- Immutability ---
lst2 = lst.append(4)
assert list(lst) == [1, 2, 3]         # Original unchanged
assert list(lst2) == [1, 2, 3, 4]     # New list with appended value

# --- Indexing and slicing ---
assert lst[0] == 1
assert lst[-1] == 3
assert list(lst[:2]) == [1, 2]

# --- Equality and hashing ---
lst_copy = COWList([1, 2, 3])
assert lst == lst_copy
assert hash(lst) == hash(lst_copy)

# --- Append ---
lst_app = lst.append(9)
assert list(lst_app) == [1, 2, 3, 9]

# --- Insert ---
lst_ins = lst.insert(1, 99)
assert list(lst_ins) == [1, 99, 2, 3]

# --- Extend ---
lst_ext = lst.extend([4, 5])
assert list(lst_ext) == [1, 2, 3, 4, 5]

# --- Delete by index ---
lst_del = lst.delete(1)
assert list(lst_del) == [1, 3]

# --- Delete by slice ---
lst_del_slice = lst.delete(slice(1, 3))
assert list(lst_del_slice) == [1]

# --- Remove value ---
lst_rem = lst.remove(2)
assert list(lst_rem) == [1, 3]

# --- Set by index ---
lst_set = lst.set(1, 42)
assert list(lst_set) == [1, 42, 3]

# --- Set by slice ---
lst_set_slice = lst.set(slice(1, 3), [7, 8])
assert list(lst_set_slice) == [1, 7, 8]

# --- Reverse ---
lst_rev = lst.reverse()
assert list(lst_rev) == [3, 2, 1]

# --- Pop ---
lst_popped, val = lst.pop()
assert list(lst_popped) == [1, 2]
assert val == 3

# --- Clear ---
lst_clear = lst.clear()
assert list(lst_clear) == []
assert lst_clear == COWList()

# --- Repr ---
assert repr(lst) == 'COWList([1, 2, 3])'

# --- Contains ---
assert 2 in lst
assert 5 not in lst

# --- Comparison ---
assert COWList([1, 2]) < COWList([1, 2, 3])
assert COWList([1, 3]) > COWList([1, 2])
```

## How It Works

Internally, COWList maintains:

- A shared physical list of elements.
- A logical offset [CanonicalRange](https://github.com/jifengwu2k/canonical-range) into that list.

On mutation, if possible, it reuses storage; otherwise, it copies only the parts it needs.

This strategy enables structural sharing and helps maintain immutability while preserving performance.

## API Reference

| Method                                                                                           | Description                                                                                                                                  |
|--------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| `__getitem__(self, index_or_slice: Union[int, slice]) -> Union[T, Self]`                         | Get element at index or sliced view of the list. O(1)                                                                                        |
| `append(self, value: T) -> Self`                                                                 | Return new instance with value appended to the end. O(1) if current instance is contiguous, O(n) if current instance is a sliced view.       |
| `extend(self, iterable: Iterable[T]) -> Self`, `__add__(self, iterable: Iterable[T]) -> Self`    | Return new instance extended with values in iterable. O(k) if current instance is contiguous, O(n + k) if current instance is a sliced view. |
| `insert(self, index: int, value: T) -> Self`                                                     | Return new instance with value inserted at index. O(n)                                                                                       |
| `delete(self, index_or_slice: Union[int, slice]) -> Self`                                        | Return new instance with element(s) at specified position(s) deleted. O(n)                                                                   |
| `set(self, index_or_slice: Union[int, slice], value_or_iterable: Union[T, Iterable[T]]) -> Self` | Return new instance with element(s) at given position(s) replaced with new value(s). O(n)                                                    |
| `pop(self, index: int = -1) -> Tuple[Self, T]`                                                   | Return (new instance with item removed, removed item), where removed item is `self[i]`. O(n)                                                 |
| `clear(self) -> Self`                                                                            | Return an empty new instance. O(1)                                                                                                           |
| `reverse(self) -> Self`                                                                          | Return a sliced view of the list with the elements in reverse order. O(1)                                                                    |

## Contributing

Contributions are welcome! Please submit pull requests or open issues on the GitHub repository.

## License

This project is licensed under the [Apache License](LICENSE).