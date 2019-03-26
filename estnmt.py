'''
Functions for estimation with NaMaster.
'''
import pymaster as nmt
import numpy as np
import healpy as hp
import sys
import os


def ini_field(mask, maps):
    '''Initialize pymaster field.'''
    print('>> Initializing the field...')
    fld = nmt.NmtField(mask, [maps])
    return fld


def ini_bin(nside, fb, sbpws=False):
    '''Initialize the set of bins.'''
    # load the file which includes bin bounds
    # two columns [lmin,lmax], both included
    print('>> Loading bin file: {}'.format(fb))
    bbs = np.loadtxt(fb, dtype='int32')
    ells = np.arange(bbs[0, 0], bbs[-1, -1] + 1, dtype='int32')
    weights = np.zeros(len(ells))
    bpws = -1 + np.zeros_like(ells)  # array of bandpower indices
    ib = 0
    for i, bb in enumerate(bbs):
        nls = bb[1] - bb[0] + 1  # number of ells in the bin
        ie = ib + nls  # not included
        weights[ib:ie] = 1. / nls
        bpws[ib:ie] = i
        ib = ie

    if sbpws:
        data = np.column_stack((ells, weights, bpws))
        header = 'ells   weights   bandpower'
        np.savetxt('bandpowers.dat', data, header=header)

    print('>> Initializing bins...')
    b = nmt.NmtBin(nside, bpws=bpws, ells=ells, weights=weights)
    return b


def est_cl(fld1, fld2, b, fwsp, swsp, me='full'):
    '''Estimate Cl.'''
    # NmtWorkspace object used to compute and store the mode coupling matrix,
    # which only depends on the masks, not on the maps
    w = nmt.NmtWorkspace()
    if os.path.isfile(fwsp):
        print('>> Loading workspace (coupling matrix) from : {}'.format(fwsp))
        w.read_from(fwsp)
    else:
        print('>> Computing coupling matrix...')
        w.compute_coupling_matrix(fld1, fld2, b)
        if fwsp != '' and swsp:
            w.write_to(fwsp)
            print(':: Workspace saved to : {}'.format(fwsp))

    if me == 'full':
        print('>> Computing full master...')
        cl = nmt.compute_full_master(fld1, fld2, b)
        cl_decoupled = cl[0]
    elif me == 'step':
        # compute the coupled full-sky angular power spectra
        # this is equivalent to Healpy.anafast on masked maps
        print('>> Computing coupled Cl...')
        cl_coupled = nmt.compute_coupled_cell(fld1, fld2)
        # decouple into bandpowers by inverting the binned coupling matrix
        print('>> Decoupling Cl...')
        cl_decoupled = w.decouple_cell(cl_coupled)[0]
    else:
        sys.exit('>> Wrong me.')

    # get the effective ells
    print('>> Getting effective ells...')
    ell = b.get_effective_ells()

    return ell, cl_decoupled


def write_cls(ell, cl, fn, fb):
    '''Write [ell, cl, xerr]s to file.'''
    bbs = np.loadtxt(fb, dtype='int32')
    xerr = (bbs[:, 1] - bbs[:, 0] + 1) / 2.
    data = np.column_stack((ell, cl, xerr))
    header = 'ell   cl   xerr'
    np.savetxt(fn, data, header=header)
    print(':: Written to: {}'.format(fn))


def main_master(args):
    '''Main function for NaMaster estimation.'''
    print('>> Loading mask 1: {}'.format(args.mask1))
    mask1 = hp.read_map(args.mask1)
    if args.fwhm1 != -1:
        print('>> Smoothing mask1, FWHM: {0:f} degrees'.format(args.fwhm1))
        fwhm1 = args.fwhm1 * np.pi / 180  # get fwhm in radians
        mask1 = hp.smoothing(mask1, fwhm=fwhm1, pol=False)

    print('>> Loading map 1: {}'.format(args.map1))
    map1 = hp.read_map(args.map1)
    field1 = ini_field(mask1, map1)

    if args.tp == 'cross':  # cross correlation
        print('>> Loading mask 2: {}'.format(args.mask2))
        mask2 = hp.read_map(args.mask2)
        if args.fwhm2 != -1:
            print('>> Smoothing mask2, FWHM: {0:f} degrees'.format(args.fwhm2))
            fwhm2 = args.fwhm2 * np.pi / 180  # get fwhm in radians
            mask2 = hp.smoothing(mask2, fwhm=fwhm2, pol=False)

        print('>> Loading map 2: {}'.format(args.map2))
        map2 = hp.read_map(args.map2)
        field2 = ini_field(mask2, map2)

    elif args.tp == 'auto':  # auto correlation
        field2 = field1

    else:
        sys.exit('>> Wrong correlation type!')

    b = ini_bin(args.nside, args.fb)

    ell, cl = est_cl(field1, field2, b, args.fwsp, args.savewsp)

    write_cls(ell, cl, args.foutcl, args.fb)