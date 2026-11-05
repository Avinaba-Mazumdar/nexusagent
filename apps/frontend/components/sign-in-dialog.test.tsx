import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vite-plus/test';
import { SignInDialog } from './sign-in-dialog';

function renderDialog() {
    return render(
        <SignInDialog
            open
            onOpenChange={() => {}}
            googleClientId=""
            gisLoaded={false}
            isGoogleLoading={false}
            isGuestLoading={false}
            error={null}
            onGuestLogin={async () => {}}
            renderGoogleButton={() => {}}
        />
    );
}

describe('SignInDialog', () => {
    it('renders the sign in options and title', () => {
        renderDialog();
        expect(screen.getByText('Sign In to AIRankAgent')).toBeInTheDocument();
        expect(screen.getByText('Sign in with Google')).toBeInTheDocument();
        expect(screen.getByText('Continue as Guest')).toBeInTheDocument();
    });
});
