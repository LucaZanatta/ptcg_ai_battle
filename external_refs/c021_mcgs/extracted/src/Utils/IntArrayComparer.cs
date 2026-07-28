using System.Collections.Generic;

namespace SabberStoneCoreAi.MCGS.Utils
{
    public class IntArrayComparer : IComparer<int[]>, IEqualityComparer<int[]>
    {
        public int Compare(int[] x, int[] y)
        {
            if (x == null)
            {
                if (y == null)
                    return 0;
                return 1;
            }

            if (y == null)
                return -1;

            if (x.Length == 0)
            {
                if (y.Length == 0)
                    return 0;
                return 1;
            }
            if (y.Length == 0)
                return -1;

            if (x[0] > y[0]) return 1;
            if (x[0] < y[0]) return -1;

            bool lengthCompare = x.Length > y.Length;
            int min = lengthCompare ? y.Length : x.Length;
            for (int i = 1; i < min; i++)
            {
                if (x[i] > y[i]) return 1;
                if (x[i] < y[i]) return -1;
            }

            if (lengthCompare) return 1;
            if (x.Length == y.Length) return 0;
            return -1;
        }

        public bool Equals(int[] x, int[] y)
        {
            if (x.Length != y.Length) return false;
            for (int i = 0; i < x.Length; i++)
                if (x[i] != y[i]) return false;
            return true;
        }

        public int GetHashCode(int[] obj)
        {
            int hc = obj.Length;
            for (int i = 0; i < obj.Length; ++i)
            {
                hc = unchecked(hc * 314159 + obj[i]);
            }
            return hc;
        }

        public static int ArrayHashCode(int[] array)
        {
            if (array == null)
                return 0;

            int hc = array.Length;
            for (int i = 0; i < array.Length; i++)
                hc = unchecked(hc * 17 + array[i]);

            return hc;
        }

        public static int ArrayHashCode(int[][] array)
        {
            if (array == null)
                return 0;
            int hc = array.Length;
            for (int i = 0; i < array.Length; i++)
                hc = unchecked(hc * 17 + ArrayHashCode(array[i]));

            return hc;
        }

        public static int ArrayHashCode(int[][][] array)
        {
            if (array == null)
                return 0;
            int hc = array.Length;
            for (int i = 0; i < array.Length; i++)
                hc = unchecked(hc * 17 + ArrayHashCode(array[i]));

            return hc;
        }
    }
}
