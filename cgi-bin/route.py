"""
Route Library
contains
    low level functions for distance calculations

Use: import route

Stuart Mackintosh - 2018
"""

import math
import numpy as np
from geopy.distance import geodesic, ELLIPSOIDS, vincenty
from collections import namedtuple

a = 6378137  # WSG84 major meters
b = 6356752.3142  # WGS84 minor meters
f = 0.0033528106647474805  # WGS84 flattening


# a = ELLIPSOIDS['WGS-84'][0] * 1000  # WSG84 major meters: 6378137
# b = ELLIPSOIDS['WGS-84'][1] * 1000  # WGS84 minor meters: 6356752.3142
# f = ELLIPSOIDS['WGS-84'][2] #WGS84 flattening

class polar(object):
    def __init__(self, lat=0, lon=0, flat=0, flon=0, shape=None, radius=0):
        self.lat = lat
        self.lon = lon
        self.flat = flat
        self.flon = flon
        self.shape = shape
        self.radius = radius


def polar2cartesian(P):
    sinPhi = math.sin(P.flat)
    cosPhi = math.cos(P.flat)
    sinLambda = math.sin(P.flon)
    cosLambda = math.cos(P.flon)
    H = 0  # $p1->{'altitude'}

    eSq = (a * a - b * b) / (a * a)
    nu = a / math.sqrt(1 - eSq * sinPhi * sinPhi)

    return np.array([(nu + H) * cosPhi * cosLambda, (nu + H) * cosPhi * sinLambda, ((1 - eSq) * nu + H) * sinPhi])


def cartesian2polar(xyz):
    eSq = (a * a - b * b) / (a * a)
    # FIX: +/- determination?
    flon = math.atan2(xyz[1], xyz[0])
    flat = math.asin(math.sqrt(xyz[2] * xyz[2] / ((1 - eSq) * a * (1 - eSq) * a + xyz[2] * xyz[2] * eSq)))

    if (xyz[2] < 0):
        flat = -flat

    lat = flat * 180 / math.pi
    lon = flon * 180 / math.pi

    return polar(lat, lon, flat, flon)


def distance(p1, p2, method='fast_andoyer'):

    if method == "fast_andoyer":
        #print ("fast andoyer")
        return fast_andoyer(p1, p2)
    elif method == "vincenty":
    #print ("vincenty")
        return vincenty((p1.lat, p1.lon), (p2.lat, p2.lon)).meters
    elif method == "geodesic":
    #print ("geodesic")
        return geodesic((p1.lat, p1.lon), (p2.lat, p2.lon)).meters
    else:
        #print ("other")
        return fast_andoyer(p1, p2)


def plane_normal(c1, c2):
    # Find the normal to the plane created by the two points ..
    # Normal n = u X v =
    #       ( (uy*vz - uz*vy), (uz*vx - ux*vz), (ux*vy - uy*vx) )
    n = np.array([c1[1] * c2[2] - c1[2] * c2[1], c1[2] * c2[0] - c1[0] * c2[2], c1[0] * c2[1] - c1[1] * c2[0]])
    return n


def vecdot(v, w):
    tl = np.dot(v, w)
    bl = np.linalg.norm(v) * np.linalg.norm(w)

    if bl == 0:
        return 1.0

    return tl / bl


def find_closest(P1, P2, P3=None, method='fast_andoyer'):
    C1 = polar2cartesian(P1)
    C2 = polar2cartesian(P2)
    if P2.shape == 'line':
        return P2

    if P3 == None:
        # End of line case ..
        O = C1 - C2
        vl = np.linalg.norm(O)
        if (vl != 0):
            O = (P2.radius / vl) * O
            CL = O + C2

        else:
            return P2
        result = cartesian2polar(CL)
        return result
    C3 = polar2cartesian(P3)
    # What if they have the same centre?
    if np.array_equal(C1, C3):
        O = C1 - C2
        vl = np.linalg.norm(O)
        if (vl < 0.01):
            # They're all the same point .. not much we can do until next iteration
            return P2

        O = (P2.radius / vl) * O
        CL = O + C2

        result = cartesian2polar(CL)
        # Keep radius for next iteration
        result.radius = P2.radius
        return result

    # What if the 1st and 2nd have the same centre?
    T = C1 - C2
    if np.linalg.norm(T) < 0.01:
        O = C3 - C2
        vl = np.linalg.norm(O)
        if vl > 0:
            O = (P2.radius / vl) * O

        CL = O + C2

        result = cartesian2polar(CL)
        return result

    u = ((C2[0] - C1[0]) * (C3[0] - C1[0]) + (C2[1] - C1[1]) * (C3[1] - C1[1]) +
         (C2[2] - C1[2]) * (C3[2] - C1[2])) / ((C3[0] - C1[0]) * (C3[0] - C1[0]) +
                                               + (C3[1] - C1[1]) * (C3[1] - C1[1])
                                               + (C3[2] - C1[2]) * (C3[2] - C1[2]))
    # print "u=$u cart dist=", vector_length($T), " polar dist=", distance($P1, $P2), "\n";

    N = C1 + (u * (C3 - C1))
    CL = N
    PR = cartesian2polar(CL)
    test = distance(PR, P2, method)
    if (u >= 0 and u <= 1) and (distance(PR, P2, method) < P2.radius):
        # Ok - we have a 180deg? connect
        # print("180 deg connect: u= radius=", P2.radius, "\n")
        return P2

    else:
        # find the angle between in/out line
        v = plane_normal(C1, C2)
        w = plane_normal(C3, C2)
        phi = math.acos(vecdot(v, w))
        phideg = phi * 180 / math.pi
        # print "    angle between in/out=$phideg\n";

        # div angle / 2 add to one of them to create new
        # vector and scale to cylinder radius for new point
        a = C1 - C2
        vla = np.linalg.norm(a)
        if vla > 0:
            a = a / vla
        b = C3 - C2
        vlb = np.linalg.norm(b)
        if vlb > 0:
            b = b / vlb
        O = a + b
        vl = np.linalg.norm(O)

        if phideg < 180:
            # print "    p2->radius=", $P2->{'radius'}, "\n";
            O = (P2.radius / vl) * O

        else:
            # print "    -p2->radius=", $P2->{'radius'}, "\n";
            O = (-P2.radius / vl) * O

        CL = O + C2

    result = cartesian2polar(CL)
    return result

def in_semicircle(self, wpts, wmade, coords):
    wpt = wpts[wmade]
    fcoords = namedtuple('fcoords', 'flat flon')  # wpts don't have flon/flat so make them for polar2cartesian
    f = fcoords(coords.lat * math.pi / 180, coords.lon * math.pi / 180)
    prev = wmade - 1
    while prev > 0 and wpt.lat == wpts[prev].lat and wpt.lon == wpts[prev].lon:
        prev -= prev

    c = polar2cartesian(wpt)
    p = polar2cartesian(wpts[prev])

    # vector that bisects the semi-circle pointing into occupied half plane
    bvec = c - p
    pvec = polar2cartesian(f) - c

    # dot product
    dot = vecdot(bvec, pvec)
    if (dot > 0):
        return 1

    return 0

def rawtime_float_to_hms(timef):
    """Converts time from floating point seconds to hours/minutes/seconds.

    Args:
        timef: A floating point time in seconds to be converted

    Returns:
        A namedtuple with hours, minutes and seconds elements
    """
    time = int(round(timef))
    hms = namedtuple('hms', ['hours', 'minutes', 'seconds'])

    return hms((time / 3600), (time % 3600) / 60, time % 60)


def distance_flown(fix, next_waypoint, short_route, distances_to_go):
    """Calculate distance flown"""

    dist_to_next = distance(fix, short_route[next_waypoint])
    dist_flown = distances_to_go[0] - (dist_to_next + distances_to_go[next_waypoint])

    return dist_flown


def fast_andoyer(p1, p2):
    flattening = f  # ELLIPSOIDS['WGS-84'][2]
    semi_major_axis = a  # ELLIPSOIDS['WGS-84'][0] * 1000

    lat1r = math.radians(p1.lat)
    lon1r = math.radians(p1.lon)
    lat2r = math.radians(p2.lat)
    lon2r = math.radians(p2.lon)

    dlon = lon2r - lon1r
    cos_dlon = math.cos(dlon)
    sin_lat1 = math.sin(lat1r)
    cos_lat1 = math.cos(lat1r)
    sin_lat2 = math.sin(lat2r)
    cos_lat2 = math.cos(lat2r)

    cos_d = sin_lat1 * sin_lat2 + cos_lat1 * cos_lat2 * cos_dlon
    if (cos_d < -1):
        cos_d = -1
    elif (cos_d > 1):
        cos_d = 1

    d = math.acos(cos_d)
    sin_d = math.sin(d)

    diffsinlat = sin_lat1 - sin_lat2
    sumsinlat = sin_lat1 + sin_lat2
    K = diffsinlat * diffsinlat
    L = sumsinlat * sumsinlat
    three_sin_d = 3 * sin_d

    one_minus_cos_d = 1 - cos_d
    one_plus_cos_d = 1 + cos_d

    if one_minus_cos_d == 0:
        H = 0
    else:
        H = (d + three_sin_d) / one_minus_cos_d

    if one_plus_cos_d == 0:
        G = 0
    else:
        G = (d - three_sin_d) / one_plus_cos_d
    dd = -(flattening / 4.0) * (H * K + G * L)
    return semi_major_axis * (d + dd)

