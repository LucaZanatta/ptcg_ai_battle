using System;
using System.Collections.Generic;

namespace SabberStoneCoreAi.MCGS.Utils
{
    public static class CommonUtils
    {
        public static readonly IntArrayComparer IntArrComparer = new IntArrayComparer();

        public static bool TryAdd<T>(this List<T> list, T item, IEqualityComparer<T> comparer)
        {
            for (int i = 0; i < list.Count; i++)
                if (comparer.Equals(list[i], item))
                    return false;

            list.Add(item);
            return true;
        }

		/// <summary>
		/// Returns a new array of elements satisfying the given predicate.
		/// </summary>
		public static T[] FilterSmallArray<T>(this T[] array, Predicate<T> predicate)
		{
			Span<int> indices = stackalloc int[array.Length];
			int k = 0;
			for (int i = 0; i < array.Length; i++)
				if (predicate(array[i]))
					indices[k++] = i;

			var result = new T[k];
			for (int i = 0; i < k; i++)
				result[i] = array[indices[i]];

			return result;
		}

		public static T[] RemoveAtIndices<T>(this T[] array, int[] indices)
        {
            Array.Sort(indices);
            var result = new T[array.Length - indices.Length];
            for (int i = 0, k = 0; i < array.Length; i++)
            {
                start:
                for (int j = k; j < indices.Length; j++)
                {
                    if (indices[j] == i)
                    {
                        k++;
                        i++;
                        if (i < array.Length)
                            goto start;
                        else
                            return result;
                    }
                }
                result[i - k] = array[i];
            }

            return result;
        }

        // ReSharper disable once InconsistentNaming
        public static double GeometricSeries(double r, int N, double T, double t) => Math.Pow(r, N) - (T / t) * r + (T / t) - 1;

        public static T GetWeightedRandom<T>(this IList<T> enumerable, Func<T, int> weightFunc, Random rnd, int totalWeight = 0)
        {
            if (totalWeight == 0)
                for (int i = 0; i < enumerable.Count; i++)
                    totalWeight += weightFunc(enumerable[i]);

            int roll = rnd.Next(totalWeight);
            T selected = default;
            for (var i = 0; i < enumerable.Count; i++)
            {
                int weight = weightFunc(enumerable[i]);
                if (roll < weight)
                {
                    selected = enumerable[i];
                    break;
                }
                roll -= weight;
            }

            return selected;
        }

        public static T GetWeightedRandom<T>(this IList<T> enumerable, Func<T, double> weightFunc, Random rnd)
        {
            double totalWeight = 0;
            for (int i = 0; i < enumerable.Count; i++)
                totalWeight += weightFunc(enumerable[i]);
            //int roll = rnd.Next(totalWeight);
            double roll = rnd.NextDouble() * totalWeight;
            T selected = default;
            for (var i = 0; i < enumerable.Count; i++)
            {
                double weight = weightFunc(enumerable[i]);
                if (roll < weight)
                {
                    selected = enumerable[i];
                    break;
                }
                roll -= weight;
            }

            return selected;
        }

        public static T GetWeightedRandom<T, F>(this IList<T> enumerable, Func<T, F, double> weightFunc, Random rnd, F optional)
        {
            double totalWeight = 0;
            for (int i = 0; i < enumerable.Count; i++)
                totalWeight += weightFunc(enumerable[i], optional);
            //int roll = rnd.Next(totalWeight);
            double roll = rnd.NextDouble() * totalWeight;
            T selected = default;
            for (var i = 0; i < enumerable.Count; i++)
            {
                double weight = weightFunc(enumerable[i], optional);
                if (roll < weight)
                {
                    selected = enumerable[i];
                    break;
                }
                roll -= weight;
            }

            return selected;
        }

        public static T Random<T>(this IList<T> list, Random rnd)
        {
			int count = list.Count;
			if (count == 0) return default;

            return list[rnd.Next(count)];
        }

        public static T[] Shuffle<T>(this T[] array, Random rnd)
        {

            for (int i = 0; i < array.Length; i++)
            {
                int r = rnd.Next(i, array.Length);
                T temp = array[i];
                array[i] = array[r];
                array[r] = temp;
            }

            return array;
        }
        public static T ArgMax<T>(this IEnumerable<T> source, Func<T, double> selector)
        {
            if (ReferenceEquals(null, source))
                throw new ArgumentNullException(nameof(source));

            if (ReferenceEquals(null, selector))
                throw new ArgumentNullException(nameof(selector));

            T maxValue = default;
            double max = 0.0;
            bool assigned = false;

            foreach (T item in source)
            {
                double v = selector(item);

                if ((v > max) || (!assigned))
                {
                    assigned = true;
                    max = v;
                    maxValue = item;
                }
            }

            return maxValue;
        }
    }
}
