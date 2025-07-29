# An immutable, copy-on-write (COW) list
# Copyright (c) 2025 Jifeng Wu
# Licensed under the Apache License. See LICENSE file in the project root for full license information.
from itertools import chain
from typing import Sequence, TypeVar, Union, Iterable, Iterator, List, Type, Sized, Optional

from canonical_range import CanonicalRange
from determine_slice_assignment_action import Insert, ReplaceOffsetRange, determine_slice_assignment_action
from tuplehash import tuplehash

T = TypeVar('T', covariant=True)


def get_items(sequence, indices):
    # type: (Sequence[T], Iterable[int]) -> Iterator[T]
    for index in indices:
        yield sequence[index]


def handle_replace_offset_range(items, offset_range, replacements):
    # type: (Iterable[T], CanonicalRange, Sequence[T]) -> Iterator[T]
    num_replacements = len(replacements)

    for offset, item in enumerate(items):
        # Replace?
        if offset in offset_range:
            replacement_offset = offset_range.index(offset)
            # Replacement available?
            if replacement_offset < num_replacements:
                yield replacements[replacement_offset]
        else:
            yield item


SelfCOWList = TypeVar('SelfCOWList', bound='COWList')


class COWList(Sequence[T]):
    """An immutable, copy-on-write (COW) list implementation.

    This class provides a persistent sequence type with copy-on-write semantics,
    where all mutating operations return new instances rather than modifying in-place.
    The implementation maintains O(1) indexing and slicing while minimizing memory usage
    through shared storage between related instances.

    Key Features:
        - Immutability: All operations return new instances, never modify in-place.
        - Copy-on-write: Underlying storage is shared until modifications are needed.
        - Efficient operations: O(1) indexing and slicing.
        - Sequence protocol: Full implementation of `collections.abc.Sequence`.
        - Hashable: Instances can be used as set elements and dict keys (when elements are hashable).

    Performance Characteristics:
        - Indexing: O(1)
        - Slicing: O(1) (creates sliced view without copying)
        - Length: O(1)
        - Append: O(1) if current instance is contiguous, O(n) if current instance is a sliced view
        - Extend: O(k) if current instance is contiguous, O(n + k) if current instance is a sliced view
        - Insert: O(n)
        - Delete: O(n)

    Example Usage:
        >>> lst = COWList([1, 2, 3])
        >>> lst2 = lst.append(4)  # Returns new instance
        >>> lst3 = lst2.insert(1, 5)  # Returns new instance
        >>> list(lst3)
        [1, 5, 2, 3, 4]

    Notes:
        - The class is covariant in its element type (T).
        - Instances cache their hash value after first computation.
        - Physical storage is shared between instances until mutations occur.

    Type Variables:
        T: Covariant type parameter representing the element type.

    Implementation Details:
        - Uses a physical implementation (list) for actual storage.
        - Tracks active elements through physical offsets (range).
        - Most operations maintain references to original storage when possible.
        - Only creates new storage when necessary (copy-on-write principle).
    """
    __slots__ = ('physical_implementation', 'physical_offset_range', 'cached_hash_value')

    def __new__(cls, iterable=()):
        # type: (Type[SelfCOWList], Iterable[T]) -> SelfCOWList
        """Create a new instance from an iterable.

        Args:
            iterable: Iterable of initial elements (default empty).

        Returns:
            New instance containing elements from iterable.
        """
        return cls._new_instance_from_in_order_physical_implementation(list(iterable))

    # Helpers
    def _new_instance_with_new_physical_offset_range(self, new_physical_offset_range):
        # type: (SelfCOWList, CanonicalRange) -> SelfCOWList
        existing_physical_implementation = self.physical_implementation

        new_instance = super(COWList, self.__class__).__new__(self.__class__)
        new_instance.physical_implementation = existing_physical_implementation
        new_instance.physical_offset_range = new_physical_offset_range
        new_instance.cached_hash_value = None

        return new_instance

    @classmethod
    def _new_instance_from_in_order_physical_implementation(cls, in_order_physical_implementation):
        # type: (Type[SelfCOWList], List[T]) -> SelfCOWList
        physical_offset_range = CanonicalRange(0, len(in_order_physical_implementation), 1)

        new_instance = super(COWList, cls).__new__(cls)
        new_instance.physical_implementation = in_order_physical_implementation
        new_instance.physical_offset_range = physical_offset_range
        new_instance.cached_hash_value = None

        return new_instance

    # COW-mutating methods
    def __add__(self, iterable):
        # type: (SelfCOWList, Iterable[T]) -> SelfCOWList
        """Return new instance extended with values in iterable.
        O(k) if current instance is contiguous, O(n + k) if current instance is a sliced view.

        Args:
            iterable: Iterable of values to extend.

        Returns:
            New instance containing original elements followed by values in iterable.
        """
        return self.insert_sequence(len(self), iterable)

    def append(self, value):
        # type: (SelfCOWList, T) -> SelfCOWList
        """Return new instance with value appended to the end.
        O(1) if current instance is contiguous, O(n) if current instance is a sliced view.

        Args:
            value: Value to append.

        Returns:
            New instance with value appended to the end.
        """
        return self.insert_sequence(len(self), (value,))

    def clear(self):
        # type: (SelfCOWList) -> SelfCOWList
        """Return an empty new instance. O(1)

        Returns:
            Empty new instance.
        """
        return self.__class__()

    def delete(self, index_or_slice):
        # type: (SelfCOWList, Union[int, slice]) -> SelfCOWList
        """Return new instance with element(s) at specified position(s) deleted. O(n)

        Args:
            index_or_slice: Either an int index or slice object.

        Returns:
            New instance with element(s) at specified position(s) deleted.

        Raises:
            IndexError: If index is out of bounds.
            TypeError: If index is neither int nor slice.
        """
        physical_implementation = self.physical_implementation  # type: List[T]
        physical_offset_range = self.physical_offset_range  # type: CanonicalRange
        length = len(physical_offset_range)  # type: int

        if isinstance(index_or_slice, int):
            # Is it valid?
            if -length <= index_or_slice < length:
                if index_or_slice < 0:
                    offset = index_or_slice + length
                else:
                    offset = index_or_slice

                physical_offset_range_left = physical_offset_range[:offset]
                physical_offset_range_right = physical_offset_range[offset + 1:]

                new_items = chain(
                    get_items(physical_implementation, physical_offset_range_left),
                    get_items(physical_implementation, physical_offset_range_right)
                )  # type: Iterable[T]

                return self.__class__(new_items)
            else:
                raise IndexError('index out of range')
        elif isinstance(index_or_slice, slice):
            sliced_out_physical_offset_range = physical_offset_range[index_or_slice]

            # Are we actually deleting?
            if not sliced_out_physical_offset_range:
                return self
            else:
                remaining_physical_offset_range = (
                    physical_offset
                    for physical_offset in physical_offset_range
                    if physical_offset not in sliced_out_physical_offset_range
                )

                new_items = get_items(physical_implementation, remaining_physical_offset_range)

                return self.__class__(new_items)
        else:
            raise TypeError('indices must be ints or slices')

    def extend(self, iterable):
        # type: (SelfCOWList, Iterable[T]) -> SelfCOWList
        """Return new instance extended with values in iterable.
        O(k) if current instance is contiguous, O(n + k) if current instance is a sliced view.

        Args:
            iterable: Iterable of values to extend.

        Returns:
            New instance containing original elements followed by values in iterable.
        """
        return self.insert_sequence(len(self), iterable)

    def insert(self, index, value):
        # type: (SelfCOWList, int, T) -> SelfCOWList
        """Return new instance with value inserted at index. O(n)

        Args:
            index: Position to insert at.
            value: Value to insert.

        Returns:
            New instance with value inserted at index.

        Raises:
            IndexError: If index is out of bounds.
        """
        return self.insert_sequence(index, (value,))

    def insert_sequence(self, index, sequence):
        # type: (SelfCOWList, Optional[int], Iterable[T]) -> SelfCOWList
        """Return new instance with values inserted at index.
        O(1) if current instance is contiguous and inserting at the end, O(n) otherwise.

        Args:
            index: Position to insert at.
            sequence: Iterable of values to insert.

        Returns:
            New instance with values inserted

        Raises:
            IndexError: If index is out of bounds
        """
        physical_implementation = self.physical_implementation  # type: List[T]
        physical_offset_range = self.physical_offset_range  # type: CanonicalRange
        length = len(physical_offset_range)  # type: int

        # Is the index valid?
        if -length <= index <= length:
            # Coerce `sequence` to an instance of `Sized`
            if not isinstance(sequence, Sized):
                sequence = list(sequence)

            sequence_length = len(sequence)

            # Is the sequence empty?
            if not sequence_length:
                return self
            else:
                physical_offset_range_left = physical_offset_range[:index]
                physical_offset_range_right = physical_offset_range[index:]

                # Are we inserting a sequence at the end of the physical implementation?
                if not physical_offset_range_right:
                    extended_physical_offset_range, extended_by = physical_offset_range.extend(sequence_length)
                    physical_length = len(physical_implementation)
                    if extended_by == CanonicalRange(physical_length, physical_length + sequence_length, 1):
                        # Fast path: directly extend current physical implementation
                        # And share it with the new instance
                        # Do not change our physical offsets or hash value,
                        # But change those of the new instance
                        physical_implementation.extend(sequence)
                        return self._new_instance_with_new_physical_offset_range(extended_physical_offset_range)

                new_items = chain(
                    get_items(physical_implementation, physical_offset_range_left),
                    sequence,
                    get_items(physical_implementation, physical_offset_range_right)
                )  # type: Iterable[T]

                return self.__class__(new_items)
        else:
            raise IndexError('index out of range')

    def pop(self, index=-1):
        # type: (SelfCOWList, int) -> tuple[SelfCOWList, T]
        """Return (new instance with item removed, removed item), where removed item is `self[i]`. O(n)

        Args:
            index: Position of item to remove (default -1).

        Returns:
            Tuple of (new instance with item removed, removed item).

        Raises:
            IndexError: If index is out of bounds.
        """
        physical_implementation = self.physical_implementation
        physical_offset_range = self.physical_offset_range
        length = len(physical_offset_range)

        if -length <= index < length:
            if index < 0:
                offset = index + length
            else:
                offset = index

            physical_offset_range_left = physical_offset_range[:offset]
            physical_offset_range_right = physical_offset_range[offset + 1:]

            popped = physical_implementation[physical_offset_range[offset]]

            new_items = chain(
                get_items(physical_implementation, physical_offset_range_left),
                get_items(physical_implementation, physical_offset_range_right)
            )  # type: Iterable[T]

            return self.__class__(new_items), popped
        else:
            raise IndexError('index out of range')

    def remove(self, value):
        # type: (SelfCOWList, T) -> SelfCOWList
        """Return new instance with first occurrence of value removed. O(n)

        Args:
            value: Value to remove.

        Returns:
            New instance with first occurrence of value removed.

        Raises:
            ValueError: If value not found in list.
        """
        physical_implementation = self.physical_implementation
        physical_offset_range = self.physical_offset_range

        # Find first occurrence of value
        element_iterator = get_items(physical_implementation, physical_offset_range)

        for offset, element in enumerate(element_iterator):
            if element == value:
                break
        else:
            raise ValueError('value not in list')

        physical_offset_range_left = physical_offset_range[:offset]
        physical_offset_range_right = physical_offset_range[offset + 1:]

        new_items = chain(
            get_items(physical_implementation, physical_offset_range_left),
            get_items(physical_implementation, physical_offset_range_right)
        )  # type: Iterable[T]

        return self.__class__(new_items)

    def reverse(self):
        # type: (SelfCOWList) -> SelfCOWList
        """Return a sliced view of the list with the elements in reverse order. O(1)

        Returns:
            Sliced view of the list with the elements in reverse order.
        """
        return self._new_instance_with_new_physical_offset_range(self.physical_offset_range[::-1])

    def set(self, index_or_slice, value_or_iterable):
        # type: (SelfCOWList, Union[int, slice], Union[T, Iterable[T]]) -> SelfCOWList
        """Return new instance with element(s) at given position(s) replaced with new value(s). O(n)

        Args:
            index_or_slice: Either an int index or slice object.
            value_or_iterable: Single value (for int) or iterable (for slice).

        Returns:
            New instance with element(s) at given position(s) replaced with new value(s).

        Raises:
            IndexError: If index is out of bounds.
            TypeError: For invalid argument combinations.
            ValueError: If slice and iterable lengths don't match.
        """
        physical_implementation = self.physical_implementation  # type: List[T]
        physical_offset_range = self.physical_offset_range  # type: CanonicalRange
        length = len(physical_offset_range)  # type: int

        if isinstance(index_or_slice, int):
            # Is it valid?
            if -length <= index_or_slice < length:
                if index_or_slice < 0:
                    offset = index_or_slice + length
                else:
                    offset = index_or_slice

                physical_offset_range_left = physical_offset_range[:offset]
                physical_offset_range_right = physical_offset_range[offset + 1:]

                new_items = chain(
                    get_items(physical_implementation, physical_offset_range_left),
                    (value_or_iterable,),
                    get_items(physical_implementation, physical_offset_range_right)
                )  # type: Iterable[T]

                return self.__class__(new_items)
            else:
                raise IndexError('index out of range')
        # Slice assignment
        elif isinstance(index_or_slice, slice):
            if isinstance(value_or_iterable, Iterable):
                assigned_sequence = list(value_or_iterable)
                assigned_sequence_length = len(assigned_sequence)

                # Determine action to take
                slice_assignment_action = determine_slice_assignment_action(length, index_or_slice)
                if isinstance(slice_assignment_action, ReplaceOffsetRange):
                    replaced_offset_range = CanonicalRange(
                        slice_assignment_action.offset_start,
                        slice_assignment_action.offset_stop,
                        slice_assignment_action.offset_step
                    )
                    replaced_offset_range_length = len(replaced_offset_range)

                    if assigned_sequence_length != replaced_offset_range_length:
                        raise ValueError(
                            'cannot assign sequence of length %d to slice of length %d' % (
                                assigned_sequence_length,
                                replaced_offset_range_length
                            )
                        )

                    new_items = handle_replace_offset_range(
                        get_items(physical_implementation, physical_offset_range),
                        replaced_offset_range,
                        assigned_sequence
                    )

                    return self.__class__(new_items)
                elif isinstance(slice_assignment_action, Insert):
                    if slice_assignment_action.reverse:
                        assigned_sequence.reverse()

                    return self.insert_sequence(slice_assignment_action.index, assigned_sequence)
                else:
                    return self
            else:
                raise TypeError('can only assign an Iterable when index is a slice')
        else:
            raise TypeError('indices must be ints or slices')

    # Sequence non-mutating methods
    def __bool__(self):
        # type: (SelfCOWList) -> bool
        return len(self.physical_offset_range) > 0

    def __contains__(self, value):
        # type: (SelfCOWList, object) -> bool
        return value in get_items(self.physical_implementation, self.physical_offset_range)

    def __eq__(self, other):
        # type: (SelfCOWList, object) -> bool
        if isinstance(other, Sequence):
            if len(self) != len(other):
                return False
            else:
                return all(a == b for a, b in zip(self, other))
        else:
            return NotImplemented

    def __getitem__(self, index_or_slice):
        # type: (SelfCOWList, Union[int, slice]) -> Union[T, SelfCOWList]
        """Get element at index or sliced view of the list. O(1)

        Args:
            index_or_slice: Either an int index or slice object.

        Returns:
            Single element if index is int, new instance if index is slice.

        Raises:
            IndexError: If index is out of bounds.
            TypeError: If index is neither int nor slice.
        """
        physical_implementation = self.physical_implementation
        physical_offset_range = self.physical_offset_range
        length = len(physical_offset_range)

        if isinstance(index_or_slice, int):
            # Is it valid?
            if -length <= index_or_slice < length:
                return physical_implementation[physical_offset_range[index_or_slice]]
            else:
                raise IndexError('index out of range')
        elif isinstance(index_or_slice, slice):
            return self._new_instance_with_new_physical_offset_range(physical_offset_range[index_or_slice])
        else:
            raise TypeError('indices must be integers or slices')

    def __hash__(self):
        # type: (SelfCOWList) -> int
        if self.cached_hash_value is not None:
            return self.cached_hash_value
        else:
            physical_implementation = self.physical_implementation
            physical_offset_range = self.physical_offset_range

            hash_value = tuplehash(
                get_items(physical_implementation, physical_offset_range),
                len(physical_offset_range)
            )

            self.cached_hash_value = hash_value

            return hash_value

    def __iter__(self):
        # type: (SelfCOWList) -> Iterator[T]
        return get_items(self.physical_implementation, self.physical_offset_range)

    def __len__(self):
        # type: (SelfCOWList) -> int
        return len(self.physical_offset_range)

    def __lt__(self, other):
        # type: (SelfCOWList, object) -> bool
        if isinstance(other, Sequence):
            for a, b in zip(self, other):
                if a < b:
                    return True
                elif b < a:
                    return False

            return len(self) < len(other)
        else:
            return NotImplemented

    def __repr__(self):
        # type: (SelfCOWList) -> str
        return '%s([%s])' % (
            self.__class__.__name__,
            ', '.join(map(repr, get_items(self.physical_implementation, self.physical_offset_range)))
        )

    def __reversed__(self):
        # type: (SelfCOWList) -> Iterator[T]
        return get_items(self.physical_implementation, reversed(self.physical_offset_range))
