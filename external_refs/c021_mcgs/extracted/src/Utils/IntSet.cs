using System;

namespace SabberStoneCoreAi.MCGS.Utils
{
	/// <summary>
	/// A efficient set implementation for small amount of <see cref="int"/> elements.
	/// </summary>
	public class IntSet
	{
		private const int INIT_SIZE = 5;

		private int[] _bucket;

		public int Count { get; set; }

		public IntSet()
		{
			_bucket = new int[INIT_SIZE];
		}

		public IntSet(int size)
		{
			_bucket = new int[size];
		}

		public bool TryAdd(int item)
		{
			var bucket = _bucket;
			if (bucket.Length == Count)
			{
				var newBucket = new int[Count * 2];
				Buffer.BlockCopy(bucket, 0, newBucket, 0, Count);
				_bucket = newBucket;
				bucket = newBucket;
			}

			for (int i = 0; i < bucket.Length; i++)
				if (bucket[i] == item)
					return false;

			bucket[Count++] = item;
			return true;
		}

		public ReadOnlySpan<int> Span => new ReadOnlySpan<int>(_bucket, 0, Count);
	}
}
